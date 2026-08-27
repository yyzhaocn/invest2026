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

# hithink
https://github.com/HiThink-Tech/Financial-API
https://fuyao.aicubes.cn/
sk-fuyao-mtBFm3u9V2gkJ6u-QOqvnqu5u6A_9ikH

skills:

hithink-finance-data         hithink-finance-fund         hithink-finance-market       hithink-finance-shared       hithink-finance-symbol       manifest.json
hithink-finance-financials   hithink-finance-index        hithink-finance-research     hithink-finance-special-data hithink-finance-valuation


command line
npm install -g @hithink-tech/hithink-finance-cli
python

https://github.com/HiThink-Tech/Financial-API/tree/main/python

```
hithink-finance 是面向 A 股的同花顺金融数据 CLI。你现在已登录（API Key 已配置），下面是从当前版本（0.1.5）能力清单整理的速查：                                                                                                               
                                                                                                                                                                                                                                              
 通用规则                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance <领域> <动词> [参数] --format json     # 机器读取一律用 json                                                                                                                                                               
   hithink-finance schema <能力id> --format json          # 查某个命令的参数契约（不确定参数时先看这个）                                                                                                                                      
   hithink-finance capabilities --format json             # 查看全部可用能力                                                                                                                                                                  
   hithink-finance <命令> --help                          # 命令级帮助                                                                                                                                                                        
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 - 大结果必须用 --output <path> 落盘，stdout 只回摘要（路径/count），不要把全量数据糊在终端。                                                                                                                                                 
 - 成功看 ok: true，失败看 error.hint 修正。                                                                                                                                                                                                  
                                                                                                                                                                                                                                              
 各领域速查                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                              
 代码搜索 / symbol                                                                                                                                                                                                                            
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance symbol search --keyword 茅台 --format json                                                                                                                                                                                 
   hithink-finance symbol list --format json              # 全市场代码表（分页）                                                                                                                                                              
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 行情 / market                                                                                                                                                                                                                                
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance market snapshot --thscode 600519.SH --format json   # 实时快照                                                                                                                                                             
   hithink-finance market history --thscode 600519.SH --output data/kline.json   # 历史K线（近10年）                                                                                                                                          
   hithink-finance market calendar --format json          # 交易日历                                                                                                                                                                          
   hithink-finance market corporate-actions --thscode ... # 复权因子                                                                                                                                                                          
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 财务 / financials                                                                                                                                                                                                                            
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance financials income --thscode ... --output ...                                                                                                                                                                               
   hithink-finance financials balance-sheet --thscode ...                                                                                                                                                                                     
   hithink-finance financials cash-flow --thscode ...                                                                                                                                                                                         
   hithink-finance financials indicators --thscode ...   # 财务指标                                                                                                                                                                           
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 估值 / valuation                                                                                                                                                                                                                             
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance valuation snapshot --thscode ...       # PE/PB/PS 快照                                                                                                                                                                     
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 指数 / index（刚用过）                                                                                                                                                                                                                       
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance index catalog --tag tszs --output ...  # 指数目录（tag: cn_concept/region/tszs/industry）                                                                                                                                  
   hithink-finance index constituents --thscode 000300.SH --output ...   # 成分股                                                                                                                                                             
   hithink-finance index snapshot / index history --thscode ...          # 指数行情                                                                                                                                                           
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 基金 / fund：fund profile|holdings|nav|returns|snapshot|history|drawdowns|manager-style|... 约 30 个能力，覆盖档案、净值、持仓、经理、分红等。                                                                                               
                                                                                                                                                                                                                                              
 特色数据 / special：limit-up-pool（涨停池）、limit-down-pool、limit-break-pool（炸板）、limit-up-ladder（连板天梯）、dragon-tiger（龙虎榜）、hot-stock（热股榜）、anomaly-list（异动）等。                                                   
                                                                                                                                                                                                                                              
 本地数据 / data + db（同步后离线查询）                                                                                                                                                                                                       
                                                                                                                                                                                                                                              
 ```bash                                                                                                                                                                                                                                      
   hithink-finance data init && hithink-finance data sync   # 初始化并同步本地 DuckDB                                                                                                                                                         
   hithink-finance data status                              # 查看本地数据状态                                                                                                                                                                
   hithink-finance db query --sql "SELECT * FROM ... LIMIT 10" --format json                                                                                                                                                                  
   hithink-finance db export --sql "..." --output out.csv                                                                                                                                                                                     
   hithink-finance market panel --output ...                # 本地全市场面板                                                                                                                                                                  
 ```                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                              
 其他                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                              
 - auth login --api-key-stdin 换 Key；auth status 查状态                                                                                                                                                                                      
 - doctor 诊断环境；skills status/sync 管理配套 skills；update --check 检查更新                                                                                                                                                               
                                                                                    
                                                                                    ```
# dsh

npx @deepseek-ai/dsh web

npm install -g @deepseek-ai/dsh

