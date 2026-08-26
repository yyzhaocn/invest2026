# book-list-with-details
find . -type d -name chapters | while read -r dir; do
    echo "========== $dir =========="
    awk '/^## / {exit} {print}' "$dir/../SKILL.md"
    echo "************************************************************************************\n"
done

# book-list-with-titles
count=0
find . -type d -name chapters | while read -r dir; do
    echo "******************************************"
    count=$((count + 1))
    echo "$count. $dir"
    if [ -f "$dir/../SKILL.md" ]; then
        awk '/^# / {flag=1} flag && /^## / {flag=0} flag' "$dir/../SKILL.md"
    else
        echo "SKILL.md not found"
    fi
done

# book list with chapters
find . -type d -name chapters -exec sh -c 'echo "========== {} =========="; grep "^# " {}/../SKILL.md; ls -al {} ;echo "******************************************\n"' \;

# SKILL summary
find . -name SKILL.md | while read -r file; do
    dir=$(dirname "$file")
    if [ ! -d "$dir/chapters" ]; then
        echo "========== $file =========="
        grep "^# " "$file"
    fi
done

# SKILL list
find . -name SKILL.md | while read -r file; do
    dir=$(dirname "$file")
    if [ ! -d "$dir/chapters" ]; then
        echo "$file"
    fi
done | sort | while read -r file; do
    echo "========== $file =========="
    grep "^# " "$file"
    echo "******************************************\n"
done

# skill-list
count=0
echo "******************************************"
find . -name SKILL.md | while read -r file; do
    dir=$(dirname "$file")
    if [ ! -d "$dir/chapters" ]; then
        echo "$file"
    fi
done | sort | while read -r file; do
    echo "******************************************"
    count=$((count + 1))
    echo "$count. $file"
    grep "^# " "$file"
done



python3 - <<'PY'                            
from easy_tdx import MacClient, Market

with MacClient.from_best_host() as c:
    df = c.get_stock_kline(Market.SH, "600519", count=10)
    print(df)
PY
