#!/usr/bin/env bash
# fix-encoding.sh — reconvertit les fichiers texte du projet en UTF-8 (sans BOM)
set -euo pipefail

# Extensions de fichiers texte à traiter
EXTENSIONS=(py txt md json js jsx ts tsx css html yml yaml toml cfg ini env sh)

# Dossiers à ignorer
PRUNE=(node_modules .git __pycache__ .venv venv dist build .vite migrations/__pycache__)

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# Vérifie la présence de iconv
command -v iconv >/dev/null || { echo "iconv requis (apt install libc-bin)"; exit 1; }

# Construit l'expression -prune pour find
prune_expr=()
for d in "${PRUNE[@]}"; do
  prune_expr+=(-path "*/$d" -prune -o)
done

# Construit l'expression des extensions
name_expr=(-false)
for e in "${EXTENSIONS[@]}"; do
  name_expr+=(-o -name "*.$e")
done

converted=0
skipped=0

while IFS= read -r -d '' file; do
  # Détecte l'encodage réel
  enc=$(file -b --mime-encoding "$file")

  case "$enc" in
    utf-8|us-ascii)
      # Déjà bon — on vérifie juste un éventuel BOM UTF-8 à retirer
      if [[ $(head -c3 "$file" | xxd -p) == "efbbbf" ]]; then
        $DRY_RUN && { echo "BOM   $file"; continue; }
        tail -c +4 "$file" > "$file.tmp" && mv "$file.tmp" "$file"
        echo "BOM retiré : $file"
        ((converted++))
      else
        ((skipped++))
      fi
      ;;
    binary)
      ((skipped++))
      ;;
    *)
      # Encodage à convertir (utf-16le, utf-16be, iso-8859-1, etc.)
      $DRY_RUN && { echo "$enc -> utf-8 : $file"; ((converted++)); continue; }
      if iconv -f "$enc" -t UTF-8 "$file" -o "$file.tmp" 2>/dev/null; then
        mv "$file.tmp" "$file"
        echo "Converti ($enc -> utf-8) : $file"
        ((converted++))
      else
        rm -f "$file.tmp"
        echo "ÉCHEC ($enc) : $file" >&2
        ((skipped++))
      fi
      ;;
  esac
done < <(find . \( "${prune_expr[@]}" -type f \( "${name_expr[@]}" \) -print0 \))

echo "---"
$DRY_RUN && echo "[DRY-RUN] $converted fichier(s) seraient modifiés, $skipped ignorés." \
         || echo "$converted fichier(s) convertis, $skipped ignorés."