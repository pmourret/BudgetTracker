from collections import Counter
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from core.tests_base import APIAuthTestCase
from imports.models import (
    Banque,
    ImportBancaire,
    LigneBancaire,
    StatutRapprochement,
)
from imports.parsers import decoder_fichier, parser_boursobank
from imports.parsers.boursobank import FormatInvalideError, _nettoyer_montant
from imports.services.rapprochement import (
    CreationFluxInvalide,
    CreationTransfertInvalide,
    ValidationInvalide,
    apparier,
    candidats_pour,
    controle_solde,
    creer_flux_depuis_ligne,
    creer_transfert_depuis_ligne,
    dernier_controle_pour_compte,
    executer_rapprochement,
    filtrer_doublons,
    flux_ids_deja_pointes,
    rejeter_ligne,
    valider_ligne,
)

# --- Fixture : extrait réel de l'export BoursoBank fourni par le foyer -------
ENTETE = (
    "dateOp;dateVal;label;suggestedLabel;category;categoryParent;amount;"
    "comment;accountNum;accountLabel;accountbalance;mark"
)
CSV_ECHANTILLON = "\n".join([
    ENTETE,
    '2026-07-17;2026-07-17;"CARTE 16/07/26 BURGERKING 13580 CB*6717";"Burger King";'
    '"Restaurants, bars, discothèques…";"Loisirs et sorties";-56,15;;00040553758;'
    '"BoursoBank (joint)";11.35;Non',
    '2026-07-10;2026-07-10;"VIR Virement depuis Compte joint";'
    '"Vir Virement Depuis Compte Joint";"Virements émis de comptes à comptes";'
    '"Mouvements internes débiteurs";"-2 469,63";;00040553758;'
    '"BoursoBank (joint)";187.45;Non',
    '2026-07-10;2026-07-10;"VIR Virement depuis CCRPM";'
    '"Vir Virement Depuis Ccrpm";"Virements reçus de comptes à comptes";'
    '"Mouvements internes créditeurs";"1 850,00";;00040553758;'
    '"BoursoBank (joint)";187.45;Non',
])


class NettoyerMontantTest(SimpleTestCase):
    """Le point le plus piégeux du format : décimale FR + milliers + guillemets."""

    def test_decimale_francaise_simple(self):
        self.assertEqual(_nettoyer_montant("-56,15"), Decimal("-56.15"))

    def test_milliers_avec_espace_et_guillemets(self):
        self.assertEqual(_nettoyer_montant('"-2 469,63"'), Decimal("-2469.63"))

    def test_credit_positif_avec_milliers(self):
        self.assertEqual(_nettoyer_montant('"1 850,00"'), Decimal("1850.00"))

    def test_espace_insecable(self):
        self.assertEqual(_nettoyer_montant("1 850,00"), Decimal("1850.00"))

    def test_montant_illisible_leve(self):
        with self.assertRaises(ValueError):
            _nettoyer_montant("abc")


class ParserBoursobankTest(SimpleTestCase):

    def test_nombre_de_lignes(self):
        res = parser_boursobank(CSV_ECHANTILLON)
        self.assertEqual(len(res.lignes), 3)
        self.assertEqual(res.erreurs, [])

    def test_signes_et_montants(self):
        res = parser_boursobank(CSV_ECHANTILLON)
        montants = [l.montant for l in res.lignes]
        self.assertEqual(montants, [
            Decimal("-56.15"), Decimal("-2469.63"), Decimal("1850.00"),
        ])

    def test_dates_et_libelles(self):
        premiere = parser_boursobank(CSV_ECHANTILLON).lignes[0]
        self.assertEqual(premiere.date_operation, date(2026, 7, 17))
        self.assertIn("BURGERKING", premiere.libelle)
        self.assertEqual(premiere.libelle_suggere, "Burger King")
        self.assertEqual(premiere.solde_apres, Decimal("11.35"))
        self.assertFalse(premiere.pointe_banque)

    def test_compte_unique_detecte(self):
        res = parser_boursobank(CSV_ECHANTILLON)
        self.assertEqual(res.comptes_rencontres, {"00040553758"})

    def test_hash_stable_et_distinct(self):
        """Deux imports du même contenu → mêmes hash (idempotence anti-doublon)."""
        h1 = [l.hash_dedup for l in parser_boursobank(CSV_ECHANTILLON).lignes]
        h2 = [l.hash_dedup for l in parser_boursobank(CSV_ECHANTILLON).lignes]
        self.assertEqual(h1, h2)
        # Les 3 lignes sont distinctes → 3 hash différents.
        self.assertEqual(len(set(h1)), 3)

    def test_ligne_illisible_non_bloquante(self):
        csv_ko = CSV_ECHANTILLON + "\n2026-07-01;2026-07-01;X;X;X;X;PASUNMONTANT;;00040553758;X;10;Non"
        res = parser_boursobank(csv_ko)
        self.assertEqual(len(res.lignes), 3)      # les bonnes lignes passent
        self.assertEqual(len(res.erreurs), 1)     # la mauvaise est signalée
        self.assertIn("Ligne 5", res.erreurs[0])

    def test_colonnes_manquantes_leve(self):
        with self.assertRaises(FormatInvalideError):
            parser_boursobank("dateOp;label;amount\n2026-07-01;X;-10,00")

    def test_fichier_vide_leve(self):
        with self.assertRaises(FormatInvalideError):
            parser_boursobank("")


class DecoderFichierTest(SimpleTestCase):

    def test_utf8_avec_bom(self):
        texte = "café ☕"
        self.assertEqual(decoder_fichier(texte.encode("utf-8-sig")), texte)

    def test_cp1252_accents(self):
        # "discothèques" encodé en Windows-1252 doit rester lisible.
        brut = "discothèques".encode("cp1252")
        self.assertEqual(decoder_fichier(brut), "discothèques")


# --- Couche PURE : anti-doublon ---------------------------------------------

def _ligne(montant, jour, h="h"):
    """Fabrique une ligne factice (duck-typing) pour les tests purs."""
    return SimpleNamespace(
        montant=Decimal(str(montant)),
        date_operation=date(2026, 7, jour),
        hash_dedup=h,
    )


def _flux(id_, montant, jour):
    return SimpleNamespace(
        id=id_,
        montant=Decimal(str(montant)),
        date_flux=date(2026, 7, jour),
    )


class FiltrerDoublonsTest(SimpleTestCase):

    def test_aucun_existant(self):
        lignes = [_ligne(-10, 1, "a"), _ligne(-20, 2, "b")]
        nouvelles, nb = filtrer_doublons(lignes, Counter())
        self.assertEqual(len(nouvelles), 2)
        self.assertEqual(nb, 0)

    def test_ecarte_les_deja_vus(self):
        lignes = [_ligne(-10, 1, "a"), _ligne(-20, 2, "b")]
        nouvelles, nb = filtrer_doublons(lignes, Counter({"a": 1}))
        self.assertEqual([l.hash_dedup for l in nouvelles], ["b"])
        self.assertEqual(nb, 1)

    def test_comptage_occurrences(self):
        # 'a' connu 1 fois : la 1re occurrence est un doublon, la 2e est neuve.
        lignes = [_ligne(-10, 1, "a"), _ligne(-10, 3, "a")]
        nouvelles, nb = filtrer_doublons(lignes, Counter({"a": 1}))
        self.assertEqual(len(nouvelles), 1)
        self.assertEqual(nb, 1)


# --- Couche PURE : matching strict ------------------------------------------

class ApparierTest(SimpleTestCase):

    def test_match_exact(self):
        res = apparier([_ligne(-56.15, 17)], [_flux(1, -56.15, 17)], tolerance_jours=3)
        d = res.decisions[0]
        self.assertEqual(d.statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(d.flux_id, 1)
        self.assertEqual(res.flux_non_apparies_ids, [])

    def test_montant_different_pas_de_match(self):
        res = apparier([_ligne(-56.15, 17)], [_flux(1, -56.16, 17)], tolerance_jours=3)
        self.assertEqual(res.decisions[0].statut, StatutRapprochement.MANQUANT_APP)
        self.assertEqual(res.flux_non_apparies_ids, [1])

    def test_tolerance_un_seul_candidat(self):
        # Date à 2 jours, dans la tolérance de 3 → rapproché automatiquement.
        res = apparier([_ligne(-56.15, 17)], [_flux(1, -56.15, 15)], tolerance_jours=3)
        self.assertEqual(res.decisions[0].statut, StatutRapprochement.RAPPROCHE)

    def test_hors_tolerance(self):
        res = apparier([_ligne(-56.15, 17)], [_flux(1, -56.15, 10)], tolerance_jours=3)
        self.assertEqual(res.decisions[0].statut, StatutRapprochement.MANQUANT_APP)

    def test_ambigu_plusieurs_candidats(self):
        # Deux flux même montant, dates 16 et 18 (Δ1), aucun exact → ambigu.
        res = apparier(
            [_ligne(-30, 17)],
            [_flux(1, -30, 16), _flux(2, -30, 18)],
            tolerance_jours=3,
        )
        d = res.decisions[0]
        self.assertEqual(d.statut, StatutRapprochement.AMBIGU)
        self.assertEqual(set(d.candidats_ids), {1, 2})

    def test_strict_prioritaire_sur_tolerance(self):
        # Flux exact (jour 17) ET flux proche (jour 16) : l'exact gagne.
        res = apparier(
            [_ligne(-30, 17)],
            [_flux(1, -30, 17), _flux(2, -30, 16)],
            tolerance_jours=3,
        )
        self.assertEqual(res.decisions[0].flux_id, 1)
        self.assertEqual(res.flux_non_apparies_ids, [2])

    def test_flux_consomme_une_seule_fois(self):
        # Deux lignes identiques, un seul flux : une rapprochée, une manquante.
        res = apparier(
            [_ligne(-30, 17), _ligne(-30, 17)],
            [_flux(1, -30, 17)],
            tolerance_jours=3,
        )
        statuts = sorted(d.statut for d in res.decisions)
        self.assertEqual(
            statuts,
            sorted([StatutRapprochement.RAPPROCHE, StatutRapprochement.MANQUANT_APP]),
        )

    def test_propagation_resout_ambiguite(self):
        # L1 (jour 17) exact avec F1 ; L2 (jour 18) proche de F1 et F2.
        # F1 consommé par L1 (exact) → L2 n'a plus que F2 → rapproché, pas ambigu.
        res = apparier(
            [_ligne(-30, 17), _ligne(-30, 18)],
            [_flux(1, -30, 17), _flux(2, -30, 20)],
            tolerance_jours=3,
        )
        self.assertEqual(res.decisions[0].flux_id, 1)
        self.assertEqual(res.decisions[1].statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(res.decisions[1].flux_id, 2)


# --- Intégration DB : orchestration + validation ----------------------------

class RapprochementDBTest(TestCase):

    def setUp(self):
        from categories.models import Categorie
        from comptes.models import Compte
        from referentiels.models import (
            Devise,
            Etablissement,
            StatutFlux,
            Titulaire,
            TypeCompte,
            TypeFlux,
        )

        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.valide = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True)
        self.previsionnel = StatutFlux.objects.create(
            code="PREV", libelle="Prévisionnel", est_definitif=False)
        self.categorie = Categorie.objects.create(code="ALIM", nom="Alimentation")
        # CREDIT est nécessaire au volet « virement interne » (transfert = une
        # paire débit/crédit) ; DEBIT seul suffisait au rapprochement 14-A.
        self.type_credit = TypeFlux.objects.create(code="CREDIT", libelle="Crédit")
        self.type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        self.titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        self.etablissement = Etablissement.objects.create(
            code="BOURSO", libelle="BoursoBank")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Joint",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
        )
        self.epargne = Compte.objects.create(
            code="CPT-0002", nom="Livret A",
            type_compte=self.type_compte,
            titulaire=self.titulaire,
            etablissement=self.etablissement,
            devise=self.devise,
        )

    def _flux(self, montant, jour, statut=None, _defaut_categorie=True, **kw):
        from flux.models import Flux
        if _defaut_categorie and "categorie" not in kw:
            kw["categorie"] = self.categorie
        return Flux.objects.create(
            compte=self.compte, type_flux=self.type_flux,
            statut=statut or self.valide, devise=self.devise,
            montant=Decimal(str(montant)), date_flux=date(2026, 7, jour), **kw,
        )

    def _lot(self, compte=None):
        return ImportBancaire.objects.create(
            compte=compte or self.compte, banque=Banque.BOURSOBANK,
            compte_num_source="00040553758")

    def _ligne_db(self, lot, montant, jour, h="h", solde=None):
        return LigneBancaire.objects.create(
            import_lot=lot, date_operation=date(2026, 7, jour),
            date_valeur=date(2026, 7, jour), libelle="TEST",
            montant=Decimal(str(montant)), hash_dedup=h,
            solde_apres=None if solde is None else Decimal(str(solde)),
        )

    def test_orchestration_statuts_et_compteurs(self):
        lot = self._lot()
        self._ligne_db(lot, "-56.15", 17, "a")   # → rapproché exact
        self._ligne_db(lot, "-99.00", 5, "b")    # → manquant dans l'app
        self._flux("-56.15", 17)                 # correspondance exacte

        rapport = executer_rapprochement(lot)
        lot.refresh_from_db()

        self.assertEqual(lot.nb_rapproches, 1)
        self.assertEqual(lot.nb_manquants_app, 1)
        self.assertEqual(len(rapport["lignes"]), 2)

    def test_transfert_rapproche(self):
        """Une ligne VIR se rapproche du flux est_transfert du compte (règle §14)."""
        lot = self._lot()
        self._ligne_db(lot, "-2469.63", 10, "vir")
        # Flux de transfert (categorie None, est_transfert=True) au bon montant.
        self._flux("-2469.63", 10, categorie=None, est_transfert=True)  # noqa: E501

        executer_rapprochement(lot)
        lot.refresh_from_db()
        self.assertEqual(lot.nb_rapproches, 1)

    def test_flux_previsionnel_non_passe_qualifie(self):
        lot = self._lot()
        self._ligne_db(lot, "-10.00", 17, "a")
        self._flux("-10.00", 17)                        # rapproché
        self._flux("-40.00", 18, statut=self.previsionnel)  # prévisionnel, absent du relevé

        rapport = executer_rapprochement(lot)
        motifs = [f["motif"] for f in rapport["flux_sans_ligne"]]
        self.assertIn("previsionnel_non_passe", motifs)

    def test_ambigu_puis_validation(self):
        lot = self._lot()
        ligne = self._ligne_db(lot, "-30.00", 17, "a")
        f1 = self._flux("-30.00", 16)   # Δ1
        self._flux("-30.00", 18)        # Δ1 → ambigu

        executer_rapprochement(lot)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.AMBIGU)
        self.assertEqual(len(candidats_pour(ligne)), 2)

        valider_ligne(ligne, f1)
        ligne.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(ligne.flux_id, f1.id)
        self.assertEqual(lot.nb_ambigus, 0)
        self.assertEqual(lot.nb_rapproches, 1)

    def test_validation_flux_non_candidat_refusee(self):
        lot = self._lot()
        ligne = self._ligne_db(lot, "-30.00", 17, "a")
        self._flux("-30.00", 16)
        self._flux("-30.00", 18)
        hors_champ = self._flux("-30.00", 1)   # hors tolérance → pas candidat
        executer_rapprochement(lot)
        with self.assertRaises(ValidationInvalide):
            valider_ligne(ligne, hors_champ)

    def test_rejet_ambigu(self):
        lot = self._lot()
        ligne = self._ligne_db(lot, "-30.00", 17, "a")
        self._flux("-30.00", 16)
        self._flux("-30.00", 18)
        executer_rapprochement(lot)

        rejeter_ligne(ligne)
        ligne.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.MANQUANT_APP)
        self.assertIsNone(ligne.flux_id)
        self.assertEqual(lot.nb_ambigus, 0)
        self.assertEqual(lot.nb_manquants_app, 1)

    # --- 14-B : création de flux + anti-re-match -----------------------------

    def test_creer_flux_depuis_ligne(self):
        lot = self._lot()
        ligne = self._ligne_db(lot, "-30.00", 17, "a")
        executer_rapprochement(lot)          # aucun flux → manquant_app
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.MANQUANT_APP)

        flux = creer_flux_depuis_ligne(ligne, categorie=self.categorie, libelle="Courses")
        ligne.refresh_from_db()
        lot.refresh_from_db()

        self.assertEqual(flux.montant, Decimal("-30.00"))
        self.assertEqual(flux.date_flux, date(2026, 7, 17))
        self.assertEqual(flux.categorie, self.categorie)
        self.assertEqual(flux.type_flux.code, "DEBIT")
        self.assertTrue(flux.statut.est_definitif)
        self.assertTrue(flux.reference_externe)          # trace bancaire posée
        self.assertEqual(ligne.flux_id, flux.id)
        self.assertEqual(ligne.statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(lot.nb_rapproches, 1)
        self.assertEqual(lot.nb_manquants_app, 0)

    def test_creer_flux_refuse_si_deja_rapproche(self):
        self._flux("-30.00", 17)
        lot = self._lot()
        ligne = self._ligne_db(lot, "-30.00", 17, "a")
        executer_rapprochement(lot)          # rapproché automatiquement
        ligne.refresh_from_db()
        with self.assertRaises(CreationFluxInvalide):
            creer_flux_depuis_ligne(ligne, categorie=self.categorie)

    # --- Virement interne créé depuis le rapprochement ----------------------

    def test_creer_transfert_depuis_ligne_sortante(self):
        """Ligne négative → le compte du relevé est la SOURCE du virement."""
        from transferts.models import Transfert

        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        executer_rapprochement(lot)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.MANQUANT_APP)

        res = creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)
        ligne.refresh_from_db()
        lot.refresh_from_db()
        transfert = res["transfert"]

        self.assertEqual(Transfert.objects.count(), 1)
        self.assertEqual(transfert.montant, Decimal("500.00"))
        self.assertEqual(transfert.flux_debit.compte, self.compte)
        self.assertEqual(transfert.flux_credit.compte, self.epargne)
        self.assertEqual(transfert.flux_debit.montant, Decimal("-500.00"))
        self.assertEqual(transfert.flux_credit.montant, Decimal("500.00"))
        self.assertTrue(transfert.flux_debit.est_transfert)
        self.assertTrue(transfert.flux_credit.est_transfert)
        self.assertEqual(transfert.flux_debit.date_flux, date(2026, 7, 17))
        self.assertIsNone(transfert.flux_debit.categorie_id)

        # La ligne pointe le flux du compte du relevé, pas la contrepartie.
        self.assertEqual(ligne.flux_id, transfert.flux_debit.id)
        self.assertEqual(ligne.statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(lot.nb_rapproches, 1)
        self.assertEqual(lot.nb_manquants_app, 0)

        # Trace bancaire sur le seul côté relevé.
        self.assertTrue(transfert.flux_debit.reference_externe)
        self.assertFalse(transfert.flux_credit.reference_externe)

    def test_creer_transfert_depuis_ligne_entrante(self):
        """Ligne positive → le compte du relevé est la DESTINATION."""
        lot = self._lot()
        ligne = self._ligne_db(lot, "500.00", 17, "a")
        executer_rapprochement(lot)
        ligne.refresh_from_db()

        res = creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)
        transfert = res["transfert"]
        ligne.refresh_from_db()

        self.assertEqual(transfert.flux_debit.compte, self.epargne)
        self.assertEqual(transfert.flux_credit.compte, self.compte)
        self.assertEqual(ligne.flux_id, transfert.flux_credit.id)

    def test_creer_transfert_refuse_contrepartie_identique(self):
        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        executer_rapprochement(lot)
        ligne.refresh_from_db()
        with self.assertRaises(CreationTransfertInvalide):
            creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.compte)

    def test_creer_transfert_refuse_si_deja_rapproche(self):
        self._flux("-500.00", 17)
        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        executer_rapprochement(lot)
        ligne.refresh_from_db()
        self.assertEqual(ligne.statut, StatutRapprochement.RAPPROCHE)
        with self.assertRaises(CreationTransfertInvalide):
            creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)

    def test_creer_transfert_rapproche_la_ligne_miroir(self):
        """Le relevé du compte d'en face, déjà importé, se solde dans la foulée."""
        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        lot_epargne = self._lot(compte=self.epargne)
        miroir = self._ligne_db(lot_epargne, "500.00", 18, "b")
        executer_rapprochement(lot)
        executer_rapprochement(lot_epargne)
        ligne.refresh_from_db()
        miroir.refresh_from_db()
        self.assertEqual(miroir.statut, StatutRapprochement.MANQUANT_APP)

        res = creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)
        miroir.refresh_from_db()
        lot_epargne.refresh_from_db()

        self.assertEqual(res["ligne_miroir"].id, miroir.id)
        self.assertEqual(miroir.statut, StatutRapprochement.RAPPROCHE)
        self.assertEqual(miroir.flux_id, res["transfert"].flux_credit.id)
        self.assertEqual(lot_epargne.nb_rapproches, 1)
        self.assertEqual(lot_epargne.nb_manquants_app, 0)

    def test_ligne_miroir_ambigue_non_devinee(self):
        """Deux lignes miroir plausibles → aucune n'est touchée (on ne devine pas)."""
        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        lot_epargne = self._lot(compte=self.epargne)
        m1 = self._ligne_db(lot_epargne, "500.00", 17, "b")
        m2 = self._ligne_db(lot_epargne, "500.00", 18, "c")
        executer_rapprochement(lot)
        executer_rapprochement(lot_epargne)
        ligne.refresh_from_db()

        res = creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)
        m1.refresh_from_db()
        m2.refresh_from_db()

        self.assertIsNone(res["ligne_miroir"])
        self.assertEqual(m1.statut, StatutRapprochement.MANQUANT_APP)
        self.assertEqual(m2.statut, StatutRapprochement.MANQUANT_APP)

    def test_transfert_cree_est_exclu_des_agregats_mais_pointe(self):
        """Le flux créé reste un transfert : hors dépenses, mais bien pointé."""
        lot = self._lot()
        ligne = self._ligne_db(lot, "-500.00", 17, "a")
        executer_rapprochement(lot)
        ligne.refresh_from_db()
        res = creer_transfert_depuis_ligne(ligne, compte_contrepartie=self.epargne)

        flux = res["flux"]
        self.assertTrue(flux.est_transfert)
        self.assertFalse(flux.est_ajustement)
        self.assertTrue(flux.statut.est_definitif)
        self.assertIn(flux.id, flux_ids_deja_pointes(self.compte))

    def test_anti_re_match_entre_lots(self):
        """Un flux déjà pointé par un lot n'est pas re-proposé à un autre lot."""
        flux_x = self._flux("-30.00", 17)
        lot1 = self._lot()
        l1 = self._ligne_db(lot1, "-30.00", 17, "h1")
        executer_rapprochement(lot1)
        l1.refresh_from_db()
        self.assertEqual(l1.flux_id, flux_x.id)          # lot1 rapproché à X

        lot2 = self._lot()
        l2 = self._ligne_db(lot2, "-30.00", 17, "h2")
        executer_rapprochement(lot2)
        l2.refresh_from_db()
        # X est déjà pointé par lot1 → exclu du vivier de lot2 → manquant.
        self.assertEqual(l2.statut, StatutRapprochement.MANQUANT_APP)

    def test_flux_ids_deja_pointes_exclut_lot_courant(self):
        flux_x = self._flux("-30.00", 17)
        lot = self._lot()
        self._ligne_db(lot, "-30.00", 17, "h1")
        executer_rapprochement(lot)
        # Vu depuis un autre point de vue, X est pointé…
        self.assertIn(flux_x.id, flux_ids_deja_pointes(self.compte))
        # …mais pas si on exclut le lot qui l'a pointé (on le recalcule à neuf).
        self.assertNotIn(flux_x.id, flux_ids_deja_pointes(self.compte, sauf_lot=lot))

    # --- Contrôle de solde ---------------------------------------------------

    def test_controle_solde_coherent(self):
        self.compte.solde_initial = Decimal("100.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-56.15", 17)                       # définitif
        lot = self._lot()
        self._ligne_db(lot, "-56.15", 17, "a", solde="43.85")  # 100 - 56.15

        ctrl = controle_solde(lot)
        self.assertEqual(ctrl["solde_app"], Decimal("43.85"))
        self.assertEqual(ctrl["ecart"], Decimal("0.00"))
        self.assertTrue(ctrl["coherent"])

    def test_controle_solde_ecart(self):
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-56.15", 17)
        lot = self._lot()
        self._ligne_db(lot, "-56.15", 17, "a", solde="-50.00")

        ctrl = controle_solde(lot)
        self.assertEqual(ctrl["ecart"], Decimal("-6.15"))
        self.assertFalse(ctrl["coherent"])

    def test_controle_solde_sur_solde_actuel(self):
        """
        On compare le solde ACTUEL (tous les flux définitifs), pas le solde à
        la date du relevé : un flux postérieur à la ligne de référence compte,
        ce qui neutralise les décalages de dates de saisie (retour d'usage prod).
        """
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-10.00", 17)
        self._flux("-100.00", 25)          # postérieur mais comptabilisé
        lot = self._lot()
        # Le relevé (dernier point au 17) a déjà, en solde final, les -110.
        self._ligne_db(lot, "-10.00", 17, "a", solde="-110.00")

        ctrl = controle_solde(lot)
        self.assertEqual(ctrl["solde_app"], Decimal("-110.00"))
        self.assertTrue(ctrl["coherent"])

    def test_controle_solde_none_sans_solde(self):
        lot = self._lot()
        self._ligne_db(lot, "-10.00", 17, "a")   # solde_apres = None
        self.assertIsNone(controle_solde(lot))

    def test_controle_solde_ignore_previsionnel(self):
        """Un flux prévisionnel ne compte pas dans le solde réel de contrôle."""
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-10.00", 17)                              # définitif
        self._flux("-40.00", 17, statut=self.previsionnel)    # prévisionnel → ignoré
        lot = self._lot()
        self._ligne_db(lot, "-10.00", 17, "a", solde="-10.00")

        ctrl = controle_solde(lot)
        self.assertEqual(ctrl["solde_app"], Decimal("-10.00"))
        self.assertTrue(ctrl["coherent"])

    # --- Contrôle par compte (hors page d'import) ---------------------------

    def test_dernier_controle_none_sans_releve(self):
        """Un compte jamais rapproché n'est pas une erreur : il n'a rien à dire."""
        self.assertIsNone(dernier_controle_pour_compte(self.compte))

    def test_dernier_controle_prend_le_point_le_plus_recent_tous_lots(self):
        """⚠️ Le cas qui motive la fonction : un vieux relevé importé APRÈS un récent.

        Ancrer le contrôle sur le dernier *lot* ferait reculer la référence et
        afficherait un écart là où il n'y en a pas. La référence est le point
        de relevé le plus récent, quel que soit l'ordre des imports.
        """
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-56.15", 17)

        recent = self._lot()
        self._ligne_db(recent, "-56.15", 17, "a", solde="-56.15")
        # Rattrapage d'un mois oublié, importé ensuite : plus vieux en date.
        ancien = self._lot()
        self._ligne_db(ancien, "-10.00", 3, "b", solde="-999.00")

        ctrl = dernier_controle_pour_compte(self.compte)
        self.assertEqual(ctrl["date_reference"], date(2026, 7, 17))
        self.assertEqual(ctrl["solde_banque"], Decimal("-56.15"))
        self.assertTrue(ctrl["coherent"])
        self.assertEqual(ctrl["import_id"], str(recent.id))

    def test_dernier_controle_anciennete_jour_injecte(self):
        """L'âge est calculé sur un jour injecté — sinon le test périme."""
        lot = self._lot()
        self._ligne_db(lot, "-10.00", 17, "a", solde="-10.00")

        ctrl = dernier_controle_pour_compte(
            self.compte, aujourd_hui=date(2026, 7, 27)
        )
        self.assertEqual(ctrl["anciennete_jours"], 10)

    def test_dernier_controle_ignore_un_lot_supprime(self):
        """Le soft delete d'un lot cascade sur ses lignes : elles sortent du calcul.

        Sans quoi supprimer un relevé erroné laisserait sa référence piloter le
        widget pour toujours.
        """
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        vivant = self._lot()
        self._ligne_db(vivant, "-10.00", 3, "a", solde="-10.00")
        efface = self._lot()
        self._ligne_db(efface, "-10.00", 17, "b", solde="-999.00")
        efface.delete()

        ctrl = dernier_controle_pour_compte(self.compte)
        self.assertEqual(ctrl["date_reference"], date(2026, 7, 3))
        self.assertEqual(ctrl["solde_banque"], Decimal("-10.00"))

    def test_dernier_controle_ignore_les_autres_comptes(self):
        """Le relevé d'un compte ne contrôle jamais le solde d'un autre."""
        from comptes.models import Compte

        autre = Compte.objects.create(
            nom="Autre", code="00099999999",
            type_compte=self.compte.type_compte,
            titulaire=self.compte.titulaire,
            etablissement=self.compte.etablissement,
            devise=self.devise, solde_initial=Decimal("0.00"),
        )
        lot = self._lot()          # rattaché à self.compte
        self._ligne_db(lot, "-10.00", 17, "a", solde="-10.00")

        self.assertIsNone(dernier_controle_pour_compte(autre))


# --- API : upload multipart + rapport + validation --------------------------

class ImportAPITest(APIAuthTestCase):

    def setUp(self):
        from categories.models import Categorie
        from comptes.models import Compte
        from flux.models import Flux
        from referentiels.models import (
            Devise,
            Etablissement,
            StatutFlux,
            Titulaire,
            TypeCompte,
            TypeFlux,
        )

        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.valide = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True)
        self.categorie = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.type_credit = TypeFlux.objects.create(code="CREDIT", libelle="Crédit")
        type_compte = TypeCompte.objects.create(code="COURANT", libelle="Courant")
        titulaire = Titulaire.objects.create(code="PIERRE", libelle="Pierre")
        etablissement = Etablissement.objects.create(code="BOURSO", libelle="BoursoBank")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Joint",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
        )
        self.epargne = Compte.objects.create(
            code="CPT-0002", nom="Livret A",
            type_compte=type_compte, titulaire=titulaire,
            etablissement=etablissement, devise=self.devise,
        )
        # Un flux app correspondant exactement à la 1re ligne du CSV échantillon.
        Flux.objects.create(
            compte=self.compte, type_flux=self.type_flux, statut=self.valide,
            devise=self.devise, categorie=self.categorie,
            montant=Decimal("-56.15"), date_flux=date(2026, 7, 17), libelle="Burger King",
        )

    def _upload(self, contenu=CSV_ECHANTILLON):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile(
            "releve.csv", contenu.encode("utf-8"), content_type="text/csv")
        return self.client.post(
            "/api/v1/imports/",
            {"compte": str(self.compte.id), "banque": "boursobank", "fichier": fichier},
            format="multipart",
        )

    def _upload_sans_compte(self, contenu=CSV_ECHANTILLON):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile(
            "releve.csv", contenu.encode("utf-8"), content_type="text/csv")
        return self.client.post(
            "/api/v1/imports/",
            {"banque": "boursobank", "fichier": fichier},
            format="multipart",
        )

    def test_upload_cree_lot_et_rapproche(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 201, resp.data)
        lot = resp.data["lot"]
        self.assertEqual(lot["nb_lignes"], 3)
        self.assertEqual(lot["nb_rapproches"], 1)   # la ligne Burger King
        self.assertEqual(lot["nb_manquants_app"], 2)

    def test_auto_resolution_compte_par_numero(self):
        # Le compte porte le numéro du fichier → résolution auto sans `compte`.
        self.compte.code = "00040553758"
        self.compte.save(update_fields=["code"])
        resp = self._upload_sans_compte()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(str(resp.data["lot"]["compte"]), str(self.compte.id))

    def test_upload_compte_introuvable_400(self):
        # Aucun compte ne porte « 00040553758 » (code par défaut = CPT-0001).
        resp = self._upload_sans_compte()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["compte_num"], "00040553758")

    def test_upload_doublons_ignores_au_second_import(self):
        self._upload()
        resp2 = self._upload()
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(resp2.data["nb_doublons"], 3)
        self.assertEqual(resp2.data["lot"]["nb_lignes"], 0)

    def test_suppression_lot_libere_les_doublons(self):
        # Un lot supprimé ne doit plus bloquer le ré-import du même relevé :
        # ses lignes sont soft-deletées en cascade (anti-doublon libéré).
        lot_id = self._upload().data["lot"]["id"]
        self.assertEqual(LigneBancaire.objects.filter(import_lot_id=lot_id).count(), 3)

        del_resp = self.client.delete(f"/api/v1/imports/{lot_id}/")
        self.assertEqual(del_resp.status_code, 204)
        self.assertEqual(LigneBancaire.objects.filter(import_lot_id=lot_id).count(), 0)

        resp2 = self._upload()
        self.assertEqual(resp2.data["nb_doublons"], 0)
        self.assertEqual(resp2.data["lot"]["nb_lignes"], 3)

    def test_upload_format_invalide_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fichier = SimpleUploadedFile("x.csv", b"colonne_bidon\n1", content_type="text/csv")
        resp = self.client.post(
            "/api/v1/imports/",
            {"compte": str(self.compte.id), "fichier": fichier},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)

    def test_rapport_detaille(self):
        lot_id = self._upload().data["lot"]["id"]
        resp = self.client.get(f"/api/v1/imports/{lot_id}/rapport/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["lignes"]), 3)
        self.assertEqual(resp.data["tolerance_jours"], 3)

    def test_creer_flux_via_api_et_badge_pointe(self):
        from flux.models import Flux
        # Flux sans rapport → doit rester non pointé.
        autre = Flux.objects.create(
            compte=self.compte, type_flux=self.type_flux, statut=self.valide,
            devise=self.devise, categorie=self.categorie,
            montant=Decimal("-5.00"), date_flux=date(2026, 1, 1))

        lot_id = self._upload().data["lot"]["id"]
        rapport = self.client.get(f"/api/v1/imports/{lot_id}/rapport/").data
        ligne = next(
            l for l in rapport["lignes"]
            if l["statut"] == "manquant_app" and l["montant"] == "-2469.63")

        resp = self.client.post(
            f"/api/v1/imports-lignes/{ligne['id']}/creer-flux/",
            {"categorie": str(self.categorie.id), "libelle": "Courses Lijak"},
            format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["ligne"]["statut"], "rapproche")
        flux_cree_id = resp.data["flux"]["id"]

        # Badge est_pointe exposé par le FluxViewSet.
        flux_list = self.client.get("/api/v1/flux/").data
        results = flux_list.get("results", flux_list)
        par_id = {f["id"]: f for f in results}
        self.assertTrue(par_id[flux_cree_id]["est_pointe"])
        self.assertFalse(par_id[str(autre.id)]["est_pointe"])

    def test_creer_transfert_via_api(self):
        """Un virement se crée depuis le rapprochement, sans passer par /transferts/."""
        lot_id = self._upload().data["lot"]["id"]
        rapport = self.client.get(f"/api/v1/imports/{lot_id}/rapport/").data
        ligne = next(
            l for l in rapport["lignes"]
            if l["statut"] == "manquant_app" and l["montant"] == "-2469.63")

        resp = self.client.post(
            f"/api/v1/imports-lignes/{ligne['id']}/creer-transfert/",
            {"compte_contrepartie": str(self.epargne.id)},
            format="json")

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["ligne"]["statut"], "rapproche")
        self.assertTrue(resp.data["flux"]["est_transfert"])
        self.assertIsNone(resp.data["ligne_miroir"])

        # Le transfert existe bien côté /transferts/, avec les deux comptes.
        transferts = self.client.get("/api/v1/transferts/").data
        results = transferts.get("results", transferts)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["compte_source_id"], str(self.compte.id))
        self.assertEqual(results[0]["compte_destination_id"], str(self.epargne.id))
        self.assertEqual(results[0]["montant"], "2469.63")

    def test_creer_transfert_refuse_meme_compte_via_api(self):
        lot_id = self._upload().data["lot"]["id"]
        rapport = self.client.get(f"/api/v1/imports/{lot_id}/rapport/").data
        ligne = next(l for l in rapport["lignes"] if l["statut"] == "manquant_app")

        resp = self.client.post(
            f"/api/v1/imports-lignes/{ligne['id']}/creer-transfert/",
            {"compte_contrepartie": str(self.compte.id)},
            format="json")
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_validation_ambigu_via_api(self):
        from flux.models import Flux
        # Deux flux -30 à J±1 → la ligne -30 du relevé sera ambiguë.
        for jour in (16, 18):
            Flux.objects.create(
                compte=self.compte, type_flux=self.type_flux, statut=self.valide,
                devise=self.devise, categorie=self.categorie,
                montant=Decimal("-30.00"), date_flux=date(2026, 7, jour))
        csv = ENTETE + '\n2026-07-17;2026-07-17;"CARTE X";X;X;X;-30,00;;00040553758;X;100;Non'
        lot_id = self._upload(csv).data["lot"]["id"]

        rapport = self.client.get(f"/api/v1/imports/{lot_id}/rapport/").data
        ligne_ambigue = next(
            l for l in rapport["lignes"] if l["statut"] == "ambigu")
        self.assertEqual(len(ligne_ambigue["candidats"]), 2)

        flux_choisi = ligne_ambigue["candidats"][0]["id"]
        resp = self.client.post(
            f"/api/v1/imports-lignes/{ligne_ambigue['id']}/valider/",
            {"flux_id": flux_choisi}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["statut"], "rapproche")

    # --- Contrôle de solde exposé hors import -------------------------------

    def _controle(self, compte_id):
        return self.client.get(
            f"/api/v1/imports/controle-compte/?compte={compte_id}")

    def test_controle_compte_apres_import(self):
        self._upload()
        resp = self._controle(self.compte.id)
        self.assertEqual(resp.status_code, 200, resp.data)
        # Montants en chaîne, comme partout ailleurs dans l'API.
        self.assertEqual(resp.data["solde_banque"], "11.35")
        self.assertIn("anciennete_jours", resp.data)
        self.assertIn("import_id", resp.data)

    def test_controle_compte_204_si_jamais_rapproche(self):
        """Pas de relevé n'est pas une erreur : le widget ne s'affiche pas, c'est tout."""
        resp = self._controle(self.compte.id)
        self.assertEqual(resp.status_code, 204)

    def test_controle_compte_sans_parametre_400(self):
        resp = self.client.get("/api/v1/imports/controle-compte/")
        self.assertEqual(resp.status_code, 400)

    def test_controle_compte_inconnu_404(self):
        import uuid
        self.assertEqual(self._controle(uuid.uuid4()).status_code, 404)

    def test_controle_compte_uuid_malforme_404_pas_500(self):
        """Une URL bricolée à la main répond « inconnu », pas « le serveur a planté »."""
        self.assertEqual(self._controle("pas-un-uuid").status_code, 404)

    def test_controle_compte_refuse_anonyme(self):
        """C'est un solde : la route ne s'ouvre pas parce qu'elle est en lecture."""
        from rest_framework.test import APIClient
        anonyme = APIClient()
        resp = anonyme.get(f"/api/v1/imports/controle-compte/?compte={self.compte.id}")
        self.assertEqual(resp.status_code, 401)
