#!/usr/bin/env bash
# fix-encoding.sh — reconvertit les fichiers texte du projet en UTF-8 (sans BOM)
set -euo pipefail

EXTENSIONS=(py txt md json js jsx ts tsx css html yml yaml toml cfg ini env sh)
PRUNE=(node_modules .git __pycache__ .venv venv dist build .vite)

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

command -v iconv >/dev/null || { echo "iconv requis (apt install libc-bin)"; exit 1; }

# Expression -prune pour les dossiers à ignorer
prune_expr=()
for d in "${PRUNE[@]}"; do
  prune_expr+=(-name "$d" -prune -o)
done

# Expression des extensions (groupée)
name_expr=()
for e in "${EXTENSIONS[@]}"; do
  name_expr+=(-o -name "*.$e")
done
name_expr=("${name_expr[@]:1}")  # retire le premier -o

converted=0
skipped=0

# Convertit $file depuis l'encodage $1 vers UTF-8 (avec gestion dry-run)
convert_file() {
  local src="$1"
  $DRY_RUN && { echo "$src -> utf-8 : $file"; ((converted++)) || true; return; }
  if iconv -f "$src" -t UTF-8 "$file" -o "$file.tmp" 2>/dev/null; then
    mv "$file.tmp" "$file"
    echo "Converti ($src -> utf-8) : $file"
    ((converted++)) || true
  else
    rm -f "$file.tmp"
    echo "ÉCHEC ($src) : $file" >&2
    ((skipped++)) || true
  fi
}

while IFS= read -r -d '' file; do
  enc=$(file -b --mime-encoding "$file")

  case "$enc" in
    utf-8|us-ascii)
      # Déjà bon — on vérifie juste un éventuel BOM UTF-8 à retirer
      if [[ $(head -c3 "$file" | od -An -tx1 | tr -d ' \n') == "efbbbf" ]]; then
        $DRY_RUN && { echo "BOM   $file"; continue; }
        tail -c +4 "$file" > "$file.tmp" && mv "$file.tmp" "$file"
        echo "BOM retiré : $file"
        ((converted++)) || true
      else
        ((skipped++)) || true
      fi
      ;;
    binary)
      # file classe aussi l'UTF-16 comme "binary" — on sonde le BOM
      bom=$(head -c2 "$file" | od -An -tx1 | tr -d ' \n')
      if [[ "$bom" == "fffe" ]]; then
        convert_file UTF-16LE
      elif [[ "$bom" == "feff" ]]; then
        convert_file UTF-16BE
      else
        ((skipped++)) || true   # vrai binaire, on ne touche pas
      fi
      ;;
    *)
      # Autres encodages texte (iso-8859-1, etc.)
      convert_file "$enc"
      ;;
  esac
done < <(find . "${prune_expr[@]}" -type f \( "${name_expr[@]}" \) -print0)

echo "---"
$DRY_RUN && echo "[DRY-RUN] $converted fichier(s) seraient modifiés, $skipped ignorés." \
         || echo "$converted fichier(s) convertis, $skipped ignorés."