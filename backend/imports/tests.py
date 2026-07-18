from collections import Counter
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from imports.parsers import decoder_fichier, parser_boursobank
from imports.parsers.boursobank import FormatInvalideError, _nettoyer_montant
from imports.models import (
    Banque, ImportBancaire, LigneBancaire, StatutRapprochement,
)
from imports.services.rapprochement import (
    ValidationInvalide, apparier, candidats_pour, controle_solde,
    executer_rapprochement, filtrer_doublons, rejeter_ligne, valider_ligne,
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
        from referentiels.models import (
            TypeCompte, Titulaire, Etablissement, Devise, TypeFlux, StatutFlux,
        )
        from comptes.models import Compte
        from categories.models import Categorie

        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.valide = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True)
        self.previsionnel = StatutFlux.objects.create(
            code="PREV", libelle="Prévisionnel", est_definitif=False)
        self.categorie = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Joint",
            type_compte=TypeCompte.objects.create(code="COURANT", libelle="Courant"),
            titulaire=Titulaire.objects.create(code="PIERRE", libelle="Pierre"),
            etablissement=Etablissement.objects.create(code="BOURSO", libelle="BoursoBank"),
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

    def _lot(self):
        return ImportBancaire.objects.create(
            compte=self.compte, banque=Banque.BOURSOBANK, compte_num_source="00040553758")

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

    def test_controle_solde_borne_a_la_date(self):
        """Un flux postérieur à la ligne de référence n'entre pas dans le solde."""
        self.compte.solde_initial = Decimal("0.00")
        self.compte.save(update_fields=["solde_initial"])
        self._flux("-10.00", 17)
        self._flux("-100.00", 25)          # postérieur → exclu
        lot = self._lot()
        self._ligne_db(lot, "-10.00", 17, "a", solde="-10.00")

        ctrl = controle_solde(lot)
        self.assertEqual(ctrl["solde_app"], Decimal("-10.00"))
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


# --- API : upload multipart + rapport + validation --------------------------

class ImportAPITest(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from referentiels.models import (
            TypeCompte, Titulaire, Etablissement, Devise, TypeFlux, StatutFlux,
        )
        from comptes.models import Compte
        from categories.models import Categorie
        from flux.models import Flux

        self.client = APIClient()
        self.devise = Devise.objects.create(
            code="EUR", libelle="Euro", symbole="€", est_defaut=True)
        self.type_flux = TypeFlux.objects.create(code="DEBIT", libelle="Débit")
        self.valide = StatutFlux.objects.create(
            code="VALIDE", libelle="Validé", est_definitif=True)
        self.categorie = Categorie.objects.create(code="ALIM", nom="Alimentation")
        self.compte = Compte.objects.create(
            code="CPT-0001", nom="Joint",
            type_compte=TypeCompte.objects.create(code="COURANT", libelle="Courant"),
            titulaire=Titulaire.objects.create(code="PIERRE", libelle="Pierre"),
            etablissement=Etablissement.objects.create(code="BOURSO", libelle="BoursoBank"),
            devise=self.devise,
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

    def test_upload_cree_lot_et_rapproche(self):
        resp = self._upload()
        self.assertEqual(resp.status_code, 201, resp.data)
        lot = resp.data["lot"]
        self.assertEqual(lot["nb_lignes"], 3)
        self.assertEqual(lot["nb_rapproches"], 1)   # la ligne Burger King
        self.assertEqual(lot["nb_manquants_app"], 2)

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
