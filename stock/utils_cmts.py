#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Comment App using East Money API
股票评论应用 - 使用东方财富API

Modules:
1. 综合评价 (Comprehensive Evaluation)
2. 主力控盘 (Main Force Control)
3. 舆情监控 (Public Opinion Monitoring)
4. 市场热度 (Market Hotness)
5. 趋势研判 (Trend Analysis)
6. 资金动向 (Capital Flow)
7. 财务评估 (Financial Evaluation)
"""

import requests
import json
import time
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EastMoneyAPI:
    """East Money API client for stock data"""
    
    def __init__(self):
        self.base_url = "https://searchadapter.eastmoney.com/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        })
    
    def _clean_jsonp_response(self, response_text: str) -> Dict:
        """Clean JSONP response and extract JSON data"""
        try:
            # Remove JSONP callback wrapper
            match = re.search(r'jQuery\d+_\d+\((.*)\);?$', response_text)
            if match:
                json_data = match.group(1)
                return json.loads(json_data)
            else:
                # Try direct JSON parsing
                return json.loads(response_text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {}

    @staticmethod
    def get_secu_code(stock_code: str) -> str:
        """Return East Money SECUCODE, e.g. 300684.SZ or 600016.SH."""
        if stock_code.startswith(("60", "68")):
            market_code = "SH"
        else:
            market_code = "SZ"
        return f"{stock_code}.{market_code}"
    
    def get_stock_evaluation(self, stock_code: str = "002916", page_size: int = None) -> Dict:
        """
        Get comprehensive stock evaluation data from East Money API
        API: RPT_DMSK_TS_STOCKEVALUATE - Comprehensive stock evaluation including main force control
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_DMSK_TS_STOCKEVALUATE',
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': '-1',  # Descending order by trade date
                '_': timestamp
            }
            
            # Add page size if specified
            if page_size:
                params['pageSize'] = page_size
            
            logger.info(f"Fetching stock evaluation data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock evaluation data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_comparison(self, stock_code: str = "002916") -> Dict:
        """
        Get stock comparison data from East Money API
        API: RPT_CUSTOM_STOCK_PK - Stock comparison and ranking data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_CUSTOM_STOCK_PK',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock comparison data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock comparison data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_change_rate(self, stock_code: str = "002916") -> Dict:
        """
        Get stock change rate and probability data from East Money API
        API: RPT_STOCK_CHANGERATE - Stock change rate and rise probability
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_STOCK_CHANGERATE',
                'pageSize': 1,
                '_': timestamp
            }
            
            logger.info(f"Fetching stock change rate data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock change rate data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_score_history(self, stock_code: str = "002916") -> Dict:
        """
        Get stock score history data from East Money API
        API: RPT_STOCK_HISTORYMARK - Historical score data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_STOCK_HISTORYMARK',
                'sortColumns': 'DIAGNOSE_DATE',
                'sortTypes': '1',  # Ascending order by date
                '_': timestamp
            }
            
            logger.info(f"Fetching stock score history for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock score history data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_pk_rank(self, stock_code: str = "002916") -> Dict:
        """
        Get stock PK ranking data from East Money API
        API: RPT_STOCK_PK_RANK - Stock ranking and comparison data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_STOCK_PK_RANK',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock PK ranking for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock PK ranking data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_industry_top_performers(self, board_code: str = "016022", page_size: int = 3) -> Dict:
        """
        Get industry top performers from East Money API
        API: RPT_STOCK_PK_RANK - Top performing stocks in industry
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': f'(BOARD_CODE="{board_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_STOCK_PK_RANK',
                'sortColumns': 'COMPRE_SCORE',
                'sortTypes': '-1',  # Descending order by score
                'pageSize': page_size,
                '_': timestamp
            }
            
            logger.info(f"Fetching industry top performers for board {board_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Industry top performers data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_market_top_performers(self, page_size: int = 10) -> Dict:
        """
        Get market top performers from East Money API
        API: RPT_STOCK_PK_RANK - Top performing stocks in market
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'filter': '',  # No filter for market-wide search
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'reportName': 'RPT_STOCK_PK_RANK',
                'sortColumns': 'COMPRE_SCORE',
                'sortTypes': '-1',  # Descending order by score
                'pageSize': page_size,
                '_': timestamp
            }
            
            logger.info(f"Fetching market top performers from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Market top performers data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_satisfaction(self, stock_code: str = "002916") -> Dict:
        """
        Get stock satisfaction data from East Money API
        API: PRT_STOCK_IS_SATISFY - Stock satisfaction indicator
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'PRT_STOCK_IS_SATISFY',
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock satisfaction data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock satisfaction data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_voice_list(self, stock_code: str = "002230", page_size: int = 20) -> Dict:
        """
        Get stock voice/list data from East Money API
        API: np-listapi.eastmoney.com - Stock voice and opinion data
        """
        try:
            url = "https://np-listapi.eastmoney.com/comm/web/getListInfo"
            params = {
                'client': 'web',
                'biz': 'web_voice',
                'mTypeAndCode': f'0.{stock_code}',
                'pageSize': page_size,
                'type': 1,
                'req_trace': f"{int(time.time() * 1000)}{int(time.time() * 1000) % 10000}"
            }
            
            logger.info(f"Fetching stock voice data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            # logger.info(f"Stock voice data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_announcements(self, stock_code: str = "002230", page_size: int = 20) -> Dict:
        """
        Get stock announcements data from East Money API
        API: np-anotice-stock.eastmoney.com - Stock announcements
        """
        try:
            url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
            params = {
                'sr': -1,
                'page_size': page_size,
                'page_index': 1,
                'ann_type': 'A',
                'client_source': 'web',
                'stock_list': stock_code,
                'f_node': 0,
                's_node': 0
            }
            
            logger.info(f"Fetching stock announcements for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            # logger.info(f"Stock announcements data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_reports(self, stock_code: str = "002230", page_size: int = 25, 
                         begin_time: str = None, end_time: str = None) -> Dict:
        """
        Get stock research reports from East Money API
        API: reportapi.eastmoney.com - Research reports
        """
        try:
            if not begin_time:
                begin_time = "2025-01-01"
            if not end_time:
                end_time = datetime.now().strftime("%Y-%m-%d")
            
            url = "https://reportapi.eastmoney.com/report/list"
            params = {
                'pageNo': 1,
                'pageSize': page_size,
                'code': stock_code,
                'industryCode': '*',
                'industry': '*',
                'rating': '*',
                'ratingchange': '*',
                'beginTime': begin_time,
                'endTime': end_time,
                'fields': '',
                'qType': 0,
                'sort': 'publishDate,desc'
            }
            
            logger.info(f"Fetching stock reports for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            # logger.info(f"Stock reports data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_participation(self, stock_code: str = "002916") -> Dict:
        """
        Get stock market participation data from East Money API
        API: RPT_STOCK_PARTICIPATION - Stock market participation willingness
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_PARTICIPATION',
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': -1,
                'pageSize': 30,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock participation data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock participation data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_market_focus(self, stock_code: str = "002916") -> Dict:
        """
        Get stock market focus data from East Money API
        API: RPT_STOCK_MARKETFOCUS - Stock market focus index
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_MARKETFOCUS',
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': -1,
                'pageSize': 30,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock market focus data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock market focus data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_comments_data(self, stock_code: str = "002916") -> Dict:
        """
        Get stock comments data from East Money API
        API: RPT_CUSTOM_STOCK_SHARES_A_THOUSAND_COMMENTS - Stock comments and updates
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_CUSTOM_STOCK_SHARES_A_THOUSAND_COMMENTS',
                'columns': 'SECURITY_CODE,SECUCODE,REPORT_NAME,UPDATE_DATE',
                'filter': f'(REPORT_NAME="STOCK_MARKET_FOCUS")(SECUCODE="{secu_code}")',
                'pageSize': 1,
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock comments data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock comments data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_trend_comment(self, stock_code: str = "002916") -> Dict:
        """
        Get stock trend comment data from East Money API
        API: RPT_STOCK_TRENDVOLUME_COMMENT - Stock trend volume comment
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_TRENDVOLUME_COMMENT',
                'columns': 'SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,TRADE_DATE,COMMENT_TXT',
                'filter': f'(SECUCODE="{secu_code}")',
                'pageSize': 1,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock trend comment data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock trend comment data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_trend_volume_data(self, stock_code: str = "002916") -> Dict:
        """
        Get stock trend volume data from East Money API
        API: RPT_CUSTOM_STOCK_SHARES_A_THOUSAND_COMMENTS - Stock trend volume data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_CUSTOM_STOCK_SHARES_A_THOUSAND_COMMENTS',
                'columns': 'REPORT_NAME,UPDATE_DATE,SECURITY_CODE,SECUCODE',
                'filter': f'(REPORT_NAME="STOCK_TREND_VOLUME")(SECUCODE="{secu_code}")',
                'pageSize': 1,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock trend volume data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock trend volume data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_price_trend(self, stock_code: str = "002916") -> Dict:
        """
        Get stock price trend data from East Money API
        API: RPT_STOCK_CHANGERATE - Stock price change rate and trend
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_CHANGERATE',
                'filter': f'(SECURITY_CODE="{stock_code}")',
                'pageSize': 1,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock price trend data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock price trend data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_stock_capital_flow(self, stock_code: str = "002916") -> Dict:
        """
        Get stock capital flow data from East Money API
        API: PRT_STOCK_CAPITALFLOWS - Individual stock capital flow data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'PRT_STOCK_CAPITALFLOWS',
                'filter': f'(SECUCODE="{secu_code}")',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': -1,
                'pageSize': 1,
                'columns': 'SECUCODE,TRADE_DATE,CAPITAL_FLOWS,CAPITAL_FLOWS_5DAYS,CAPITAL_FLOWS_RATIO,CAPITAL_FLOWS_5DAYSRATIO',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching stock capital flow data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Stock capital flow data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_industry_capital_flow(self, stock_code: str = "002916") -> Dict:
        """
        Get industry capital flow data from East Money API
        API: PRT_STOCK_CAPITALFLOWS - Industry capital flow data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'PRT_STOCK_CAPITALFLOWS',
                'filter': f'(SECUCODE="{secu_code}")',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': -1,
                'pageSize': 10,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching industry capital flow data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Industry capital flow data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_industry_ranking_data(self, stock_code: str = "002916") -> Dict:
        """
        Get industry ranking data from East Money API
        API: PRT_STOCK_CAPITALFLOWS - Industry ranking comparison
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'PRT_STOCK_CAPITALFLOWS',
                'filter': f'(SECUCODE="{secu_code}")',
                'sortColumns': 'CAPITAL_FLOWS',
                'sortTypes': -1,
                'pageSize': 5,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching industry ranking data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Industry ranking data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_dragon_tiger_board(self, stock_code: str = "002916") -> Dict:
        """
        Get dragon tiger board data from East Money API
        API: RPT_STOCK_LHB5DAYS - Dragon Tiger Board data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_LHB5DAYS',
                'filter': f'(SECUCODE="{secu_code}")',
                'pageSize': 10,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching dragon tiger board data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Dragon tiger board data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_margin_trading(self, stock_code: str = "002916") -> Dict:
        """
        Get margin trading data from East Money API
        API: RPT_STOCK_MARGINTREND - Margin Trading data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_STOCK_MARGINTREND',
                'filter': f'(SECUCODE="{secu_code}")',
                'sortColumns': 'TRADE_DATE',
                'sortTypes': -1,
                'pageSize': 30,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching margin trading data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Margin trading data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}
    
    def get_financial_evaluation(self, stock_code: str = "002916") -> Dict:
        """
        Get financial evaluation data from East Money API
        API: RPT_APP_BALANCED_PICTURE - Financial evaluation data
        """
        try:
            # Generate timestamp for cache busting
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            
            secu_code = self.get_secu_code(stock_code)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_APP_BALANCED_PICTURE',
                'filter': f'(SECUCODE="{secu_code}")',
                'pageSize': 200,
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                '_': timestamp
            }
            
            logger.info(f"Fetching financial evaluation data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Clean and parse the JSONP response
            data = self._clean_jsonp_response(response.text)
            
            # logger.info(f"Financial evaluation data response: {data}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}

    def get_financial_analysis(self, stock_code: str = "002916", page_size: int = 2) -> Dict:
        """
        Get financial analysis data from East Money API
        API: RPT_F10_FINANALYSIS - Financial ratios and industry rankings
        """
        try:
            timestamp = int(time.time() * 1000)
            cb_name = f"jQuery{timestamp}_{timestamp + 1}"
            secu_code = self.get_secu_code(stock_code)

            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                'callback': cb_name,
                'reportName': 'RPT_F10_FINANALYSIS',
                'filter': f'(SECUCODE="{secu_code}")',
                'columns': 'ALL',
                'source': 'WEB',
                'client': 'WEB',
                'sortColumns': 'REPORT_DATE',
                'sortTypes': '-1',
                'pageSize': page_size,
                '_': timestamp
            }

            logger.info(f"Fetching financial analysis data for {stock_code} from: {url}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return self._clean_jsonp_response(response.text)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"error": str(e)}


class StockCommentApp:
    """Main Stock Comment Application with caching support"""
    
    def __init__(self, cache_enabled: bool = True, cache_dir: str = "../generated/cache/stockd"):
        self.api = EastMoneyAPI()
        self.current_module = 1
        self.cache_enabled = cache_enabled
        
        if cache_enabled:
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.cache_duration = timedelta(hours=3)
    
    def _get_cache_file(self, stock_code: str, module: str) -> Path:
        """Get cache file path for a stock and module"""
        stock_dir = self.cache_dir / stock_code
        stock_dir.mkdir(exist_ok=True)
        return stock_dir / f"module_{module}.json"
    
    def _is_trading_time(self) -> bool:
        """Check if current time is trading time"""
        now = datetime.now()
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Non-trading days (Saturday, Sunday)
        if weekday >= 5:
            return False
        
        # Check if it's a holiday
        date_str = now.strftime('%Y-%m-%d')
        holidays = {
            # 2025 Chinese National Day holiday: Oct 1-8
            '2025-10-01': '国庆节',
            '2025-10-02': '国庆节',
            '2025-10-03': '国庆节',
            '2025-10-04': '国庆节',
            '2025-10-05': '国庆节',
            '2025-10-06': '国庆节',
            '2025-10-07': '国庆节',
            '2025-10-08': '国庆节',
        }
        
        if date_str in holidays:
            return False
        
        # Check trading hours
        current_time = now.time()
        morning_start = datetime.strptime('09:30', '%H:%M').time()
        morning_end = datetime.strptime('11:30', '%H:%M').time()
        afternoon_start = datetime.strptime('13:00', '%H:%M').time()
        afternoon_end = datetime.strptime('15:00', '%H:%M').time()
        
        return (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end)
    
    def _is_stale_module_cache(self, module: str, data: Dict) -> bool:
        """Invalidate cache when module payload schema is outdated."""
        if module == "7":
            raw_data = data.get("raw_data") or {}
            if "financial_analysis" not in raw_data:
                return True
            if data.get("total_data_sources", 1) < 2:
                return True
        return False

    def _get_cached_data(self, stock_code: str, module: str) -> Optional[Dict]:
        """
        Get cached data if it exists and is not expired
        
        Args:
            stock_code: Stock code (e.g., "002916")
            module: Module number (e.g., "1", "2", etc.)
        
        Returns:
            Cached data dict if valid, None otherwise
        """
        if not self.cache_enabled:
            return None
            
        cache_file = self._get_cache_file(stock_code, module)
        
        if not cache_file.exists():
            logger.info(f"Cache miss: {stock_code} module_{module}")
            return None
        
        try:
            file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)

            try:
                from stock.module_cache_policy import is_cache_expired
            except ImportError:
                from module_cache_policy import is_cache_expired

            if is_cache_expired(file_mtime):
                logger.info(f"Cache expired: {stock_code} module_{module}, past next trading day 16:30")
                return None

            # Load and return cached data
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if self._is_stale_module_cache(module, data):
                logger.info(f"Cache schema outdated: {stock_code} module_{module}")
                return None
            
            logger.info(f"Cache hit: {stock_code} module_{module}")
            return data
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None
    
    def _cache_data(self, stock_code: str, module: str, data: Dict) -> bool:
        """
        Save data to cache
        
        Args:
            stock_code: Stock code
            module: Module number
            data: Data to cache
        
        Returns:
            True if successful, False otherwise
        """
        if not self.cache_enabled:
            return False
            
        cache_file = self._get_cache_file(stock_code, module)
        logger.info(f"Saving cache to: {cache_file}")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cached: {stock_code} module_{module}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            return False
    
    def _run_module_with_cache(self, stock_code: str, module_num: int, module_func) -> Dict:
        """
        Run a module with caching support
        
        Args:
            stock_code: Stock code
            module_num: Module number
            module_func: The actual module function to run
        
        Returns:
            Module data dict
        """
        # Try to get from cache first
        cached_data = self._get_cached_data(stock_code, str(module_num))
        if cached_data:
            print(f"✓ Using cached data for {stock_code} module_{module_num}")
            return cached_data
        
        # Fetch fresh data
        try:
            print(f"⬇ Fetching fresh data for {stock_code} module_{module_num}")
            data = module_func(stock_code)
            
            # Cache the data
            self._cache_data(stock_code, str(module_num), data)
            
            return data
            
        except Exception as e:
            print(f"⚠ Error fetching module_{module_num} for {stock_code}: {e}")
            return {"error": str(e)}
        
    def run_module_1(self, stock_code: str = "002916") -> Dict:
        """
        Module 1: 综合评价 (Comprehensive Evaluation)
        获取股票的综合评价数据，包括主力控盘、满意度指标、历史评分、排名对比等全方位分析
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 1: 综合评价 (Comprehensive Evaluation) for stock {stock_code}")
            
            # Get comprehensive stock evaluation data (includes main force control)
            evaluation_data = self.api.get_stock_evaluation(stock_code)
            
            # Get paginated evaluation data (22 records)
            evaluation_data_paginated = self.api.get_stock_evaluation(stock_code, page_size=22)
            
            # Get stock satisfaction data
            satisfaction_data = self.api.get_stock_satisfaction(stock_code)
            
            # Get stock comparison data
            comparison_data = self.api.get_stock_comparison(stock_code)
            
            # Get stock change rate and probability data
            change_rate_data = self.api.get_stock_change_rate(stock_code)
            
            # Get stock score history
            score_history_data = self.api.get_stock_score_history(stock_code)
            
            # Get stock PK ranking data
            pk_rank_data = self.api.get_stock_pk_rank(stock_code)
            
            # Get industry top performers (assuming electronics components industry)
            industry_top_data = self.api.get_industry_top_performers("016022", 3)
            
            # Get market top performers
            market_top_data = self.api.get_market_top_performers(10)
            
            # Process and combine the data
            comprehensive_evaluation = {
                "evaluation_analysis": evaluation_data,
                "evaluation_analysis_paginated": evaluation_data_paginated,
                "satisfaction_analysis": satisfaction_data,
                "comparison_analysis": comparison_data,
                "change_rate_analysis": change_rate_data,
                "score_history_analysis": score_history_data,
                "pk_ranking_analysis": pk_rank_data,
                "industry_top_performers": industry_top_data,
                "market_top_performers": market_top_data,
                "evaluation_summary": self._generate_evaluation_summary(
                    evaluation_data, satisfaction_data, comparison_data, 
                    change_rate_data, score_history_data, pk_rank_data,
                    industry_top_data, market_top_data
                )
            }
            
            # Check for errors
            data_sources = [
                evaluation_data, satisfaction_data, comparison_data,
                change_rate_data, score_history_data, pk_rank_data,
                industry_top_data, market_top_data
            ]
            has_errors = any("error" in data for data in data_sources)
            successful_sources = sum(1 for data in data_sources if "error" not in data)
            
            result = {
                "module": "综合评价 (Comprehensive Evaluation)",
                "stock_code": stock_code,
                "timestamp": datetime.now().isoformat(),
                "data": comprehensive_evaluation,
                "status": "success" if not has_errors else "partial_success" if successful_sources > 0 else "error",
                "data_sources_available": successful_sources,
                "total_data_sources": len(data_sources)
            }
            
            return result
        
        return self._run_module_with_cache(stock_code, 1, _fetch_data)
    
    def _generate_evaluation_summary(self, evaluation_data: Dict, satisfaction_data: Dict, comparison_data: Dict = None,
                                   change_rate_data: Dict = None, score_history_data: Dict = None, pk_rank_data: Dict = None,
                                   industry_top_data: Dict = None, market_top_data: Dict = None) -> Dict:
        """Generate a comprehensive evaluation summary"""
        summary = {
            "overall_score": 0,
            "main_force_score": 0,
            "satisfaction_score": 0,
            "comparison_score": 0,
            "change_rate_score": 0,
            "historical_score": 0,
            "ranking_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "key_metrics": {},
            "comparison_metrics": {},
            "historical_metrics": {},
            "ranking_metrics": {},
            "industry_comparison": {},
            "market_position": {}
        }
        
        # Analyze comprehensive evaluation data (main force control)
        if "error" not in evaluation_data and "result" in evaluation_data:
            result_data = evaluation_data["result"]
            if "data" in result_data and result_data["data"]:
                latest_data = result_data["data"][0]  # Most recent data
                stock_name = latest_data.get("SECURITY_NAME_ABBR", "Unknown")
                
                # Extract key metrics
                close_price = latest_data.get("CLOSE_PRICE", 0)
                change_rate = latest_data.get("CHANGE_RATE", 0)
                turnover_rate = latest_data.get("TURNOVERRATE", 0)
                pe_ratio = latest_data.get("PE_DYNAMIC", 0)
                participate_ratio = latest_data.get("ORG_PARTICIPATE", 0)
                participate_type_cn = latest_data.get("PARTICIPATE_TYPE_CN", "未知")
                
                summary["key_metrics"] = {
                    "close_price": close_price,
                    "change_rate": change_rate,
                    "turnover_rate": turnover_rate,
                    "pe_ratio": pe_ratio,
                    "participate_ratio": participate_ratio,
                    "participate_type": participate_type_cn
                }
                
                # Calculate main force score based on participation and control
                main_force_score = 0
                if participate_ratio > 0.4:  # High participation
                    main_force_score += 40
                elif participate_ratio > 0.3:
                    main_force_score += 25
                
                if "完全控盘" in participate_type_cn:
                    main_force_score += 40
                elif "中度控盘" in participate_type_cn:
                    main_force_score += 25
                elif "轻度控盘" in participate_type_cn:
                    main_force_score += 10
                
                # Adjust based on recent performance
                if change_rate > 0:
                    main_force_score += 20
                elif change_rate > -2:
                    main_force_score += 10
                
                summary["main_force_score"] = min(main_force_score, 100)
                
                summary["analysis"].append(f"{stock_name} 主力控盘类型: {participate_type_cn}")
                summary["analysis"].append(f"机构参与度: {participate_ratio:.2%}")
                summary["analysis"].append(f"主力控盘评分: {summary['main_force_score']}/100")
                summary["analysis"].append(f"收盘价: ¥{close_price}")
                summary["analysis"].append(f"涨跌幅: {change_rate:.2f}%")
                tr_display = turnover_rate if abs(turnover_rate) > 1 else turnover_rate * 100
                summary["analysis"].append(f"换手率: {tr_display:.2f}%")
            else:
                summary["analysis"].append("评价数据为空")
        else:
            summary["analysis"].append("评价数据获取失败")
        
        # Analyze satisfaction data
        if "error" not in satisfaction_data and "result" in satisfaction_data:
            result_data = satisfaction_data["result"]
            if "data" in result_data and result_data["data"]:
                stock_info = result_data["data"][0]
                is_satisfy = stock_info.get("IS_SATISFY", "0")
                stock_name = stock_info.get("SECURITY_NAME_ABBR", "Unknown")
                
                summary["satisfaction_score"] = 80 if is_satisfy == "1" else 20
                summary["analysis"].append(f"{stock_name} 满意度指标: {'满足' if is_satisfy == '1' else '不满足'}")
                summary["analysis"].append(f"满意度评分: {summary['satisfaction_score']}/100")
            else:
                summary["analysis"].append("满意度数据为空")
        else:
            summary["analysis"].append("满意度数据获取失败")
        
        # Analyze comparison data
        if comparison_data and "error" not in comparison_data and "result" in comparison_data:
            result_data = comparison_data["result"]
            if "data" in result_data and result_data["data"]:
                comparison_info = result_data["data"][0]
                
                # Extract comparison metrics
                total_score = comparison_info.get("TOTALSCORE", 0)
                rank = comparison_info.get("RANK", None)
                rank_up = comparison_info.get("RANK_UP", None)
                focus = comparison_info.get("FOCUS", None)
                
                summary["comparison_metrics"] = {
                    "total_score": total_score,
                    "rank": rank,
                    "rank_up": rank_up,
                    "focus": focus
                }
                
                # Calculate comparison score
                if total_score is not None:
                    summary["comparison_score"] = min(total_score * 2, 100)  # Scale to 0-100
                    summary["analysis"].append(f"综合评分: {total_score} ({summary['comparison_score']}/100)")
                
                if rank is not None:
                    summary["analysis"].append(f"排名: {rank}")
                
                if rank_up is not None:
                    summary["analysis"].append(f"排名变化: {rank_up}")
                
                if focus is not None:
                    summary["analysis"].append(f"关注度: {focus}")
            else:
                summary["analysis"].append("对比数据为空")
        else:
            summary["analysis"].append("对比数据获取失败")
        
        # Analyze change rate data
        if change_rate_data and "error" not in change_rate_data and "result" in change_rate_data:
            result_data = change_rate_data["result"]
            if "data" in result_data and result_data["data"]:
                change_info = result_data["data"][0]
                total_score = change_info.get("TOTAL_SCORE", 0)
                rise_1_prob = change_info.get("RISE_1_PROBABILITY", 0)
                rise_5_prob = change_info.get("RISE_5_PROBABILITY", 0)
                
                summary["change_rate_score"] = min(total_score * 1.4, 100)  # Scale to 0-100
                summary["analysis"].append(f"涨跌概率评分: {total_score:.2f} ({summary['change_rate_score']}/100)")
                summary["analysis"].append(f"1日上涨概率: {rise_1_prob:.1f}%")
                summary["analysis"].append(f"5日上涨概率: {rise_5_prob:.1f}%")
            else:
                summary["analysis"].append("涨跌概率数据为空")
        else:
            summary["analysis"].append("涨跌概率数据获取失败")
        
        # Analyze score history data
        if score_history_data and "error" not in score_history_data and "result" in score_history_data:
            result_data = score_history_data["result"]
            if "data" in result_data and result_data["data"]:
                history_data = result_data["data"]
                latest_score = history_data[-1].get("TOTAL_SCORE", 0) if history_data else 0
                score_trend = self._calculate_score_trend(history_data)
                
                summary["historical_score"] = min(latest_score * 1.4, 100)
                summary["historical_metrics"] = {
                    "latest_score": latest_score,
                    "score_trend": score_trend,
                    "data_points": len(history_data)
                }
                summary["analysis"].append(f"历史评分: {latest_score:.2f} ({summary['historical_score']}/100)")
                summary["analysis"].append(f"评分趋势: {score_trend}")
            else:
                summary["analysis"].append("历史评分数据为空")
        else:
            summary["analysis"].append("历史评分数据获取失败")
        
        # Analyze PK ranking data
        if pk_rank_data and "error" not in pk_rank_data and "result" in pk_rank_data:
            result_data = pk_rank_data["result"]
            if "data" in result_data and result_data["data"]:
                rank_info = result_data["data"][0]
                compre_score = rank_info.get("COMPRE_SCORE", 0)
                market_rank = rank_info.get("MARKET_RANK", 0)
                industry_rank = rank_info.get("INDUSTRY_RANK", 0)
                stock_rank_ratio = rank_info.get("STOCK_RANK_RATIO", 0)
                board_name = rank_info.get("BOARD_NAME", "Unknown")
                
                summary["ranking_score"] = min(compre_score * 1.4, 100)
                summary["ranking_metrics"] = {
                    "comprehensive_score": compre_score,
                    "market_rank": market_rank,
                    "industry_rank": industry_rank,
                    "rank_percentile": stock_rank_ratio,
                    "industry": board_name
                }
                summary["analysis"].append(f"综合评分: {compre_score:.2f} ({summary['ranking_score']}/100)")
                summary["analysis"].append(f"市场排名: {market_rank}")
                summary["analysis"].append(f"行业排名: {industry_rank} ({board_name})")
                summary["analysis"].append(f"排名百分位: {stock_rank_ratio:.1f}%")
            else:
                summary["analysis"].append("排名数据为空")
        else:
            summary["analysis"].append("排名数据获取失败")
        
        # Analyze industry comparison
        if industry_top_data and "error" not in industry_top_data and industry_top_data.get("result"):
            result_data = industry_top_data["result"]
            if result_data and "data" in result_data and result_data["data"]:
                industry_stocks = result_data["data"]
                summary["industry_comparison"] = {
                    "top_performers": [
                        {
                            "name": stock.get("SECURITY_NAME_ABBR", "Unknown"),
                            "code": stock.get("SECURITY_CODE", "Unknown"),
                            "score": stock.get("COMPRE_SCORE", 0),
                            "rank": stock.get("INDUSTRY_RANK", 0)
                        } for stock in industry_stocks
                    ],
                    "total_industry_stocks": result_data.get("count", 0)
                }
                summary["analysis"].append(f"行业对比: 共{result_data.get('count', 0)}只股票")
            else:
                summary["analysis"].append("行业对比数据为空")
        else:
            summary["analysis"].append("行业对比数据获取失败")
        
        # Analyze market position
        if market_top_data and "error" not in market_top_data and market_top_data.get("result"):
            result_data = market_top_data["result"]
            if result_data and "data" in result_data and result_data["data"]:
                market_stocks = result_data["data"]
                summary["market_position"] = {
                    "top_performers": [
                        {
                            "name": stock.get("SECURITY_NAME_ABBR", "Unknown"),
                            "code": stock.get("SECURITY_CODE", "Unknown"),
                            "score": stock.get("COMPRE_SCORE", 0),
                            "rank": stock.get("MARKET_RANK", 0)
                        } for stock in market_stocks
                    ],
                    "total_market_stocks": result_data.get("count", 0)
                }
                summary["analysis"].append(f"市场对比: 共{result_data.get('count', 0)}只股票")
            else:
                summary["analysis"].append("市场对比数据为空")
        else:
            summary["analysis"].append("市场对比数据获取失败")
        
        # Calculate overall score
        valid_scores = [
            s for s in [
                summary["main_force_score"], summary["satisfaction_score"], 
                summary["comparison_score"], summary["change_rate_score"],
                summary["historical_score"], summary["ranking_score"]
            ] if s > 0
        ]
        if valid_scores:
            summary["overall_score"] = sum(valid_scores) / len(valid_scores)
        
        # Generate recommendation
        if summary["overall_score"] >= 70:
            summary["recommendation"] = "positive"
        elif summary["overall_score"] >= 40:
            summary["recommendation"] = "neutral"
        else:
            summary["recommendation"] = "negative"
        
        return summary
    
    def _calculate_score_trend(self, history_data: List[Dict]) -> str:
        """Calculate score trend from historical data"""
        if len(history_data) < 2:
            return "数据不足"
        
        recent_scores = [item.get("TOTAL_SCORE", 0) for item in history_data[-5:]]  # Last 5 days
        if len(recent_scores) < 2:
            return "数据不足"
        
        avg_recent = sum(recent_scores) / len(recent_scores)
        
        if len(history_data) >= 10:
            earlier_scores = [item.get("TOTAL_SCORE", 0) for item in history_data[-10:-5]]
            avg_earlier = sum(earlier_scores) / len(earlier_scores)
        else:
            avg_earlier = avg_recent
        
        if avg_recent > avg_earlier * 1.02:
            return "上升"
        elif avg_recent < avg_earlier * 0.98:
            return "下降"
        else:
            return "稳定"
    
    def run_module_2(self, stock_code: str = "002916") -> Dict:
        """
        Module 2: 主力控盘 (Main Force Control)
        分析主力资金控盘情况，包括机构参与度、主力净流入、主力成本、控盘类型等关键指标
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 2: 主力控盘 (Main Force Control) for stock {stock_code}")
            
            # Get comprehensive stock evaluation data (includes main force control)
            evaluation_data = self.api.get_stock_evaluation(stock_code)
            
            # Get stock PK ranking data for comparison
            pk_rank_data = self.api.get_stock_pk_rank(stock_code)
            
            # Get stock comparison data
            comparison_data = self.api.get_stock_comparison(stock_code)
            
            # Get stock change rate and probability data
            change_rate_data = self.api.get_stock_change_rate(stock_code)
            
            # Get industry top performers for comparison
            industry_top_data = self.api.get_industry_top_performers("016022", 5)
            
            # Process and analyze the main force control data
            main_force_analysis = {
                "evaluation_analysis": evaluation_data,
                "pk_ranking_analysis": pk_rank_data,
                "comparison_analysis": comparison_data,
                "change_rate_analysis": change_rate_data,
                "industry_comparison": industry_top_data,
                "main_force_summary": self._generate_main_force_summary(
                    evaluation_data, pk_rank_data, comparison_data, 
                    change_rate_data, industry_top_data
                )
            }
            
            # Check for errors
            data_sources = [
                evaluation_data, pk_rank_data, comparison_data,
                change_rate_data, industry_top_data
            ]
            has_errors = any("error" in data for data in data_sources)
            successful_sources = sum(1 for data in data_sources if "error" not in data)
            
            result = {
                "module": "主力控盘 (Main Force Control)",
                "stock_code": stock_code,
                "timestamp": datetime.now().isoformat(),
                "data": main_force_analysis,
                "status": "success" if not has_errors else "partial_success" if successful_sources > 0 else "error",
                "data_sources_available": successful_sources,
                "total_data_sources": len(data_sources)
            }
            
            return result
        
        return self._run_module_with_cache(stock_code, 2, _fetch_data)
    
    def _generate_main_force_summary(self, evaluation_data: Dict, pk_rank_data: Dict = None,
                                   comparison_data: Dict = None, change_rate_data: Dict = None,
                                   industry_top_data: Dict = None) -> Dict:
        """Generate main force control analysis summary"""
        summary = {
            "overall_control_score": 0,
            "institutional_participation_score": 0,
            "main_force_flow_score": 0,
            "control_type_score": 0,
            "cost_analysis_score": 0,
            "performance_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "key_metrics": {},
            "control_indicators": {},
            "flow_indicators": {},
            "cost_indicators": {},
            "industry_position": {},
            "risk_assessment": {}
        }
        
        # Analyze comprehensive evaluation data (main force control)
        if "error" not in evaluation_data and "result" in evaluation_data:
            result_data = evaluation_data["result"]
            if "data" in result_data and result_data["data"]:
                latest_data = result_data["data"][0]  # Most recent data
                stock_name = latest_data.get("SECURITY_NAME_ABBR", "Unknown")
                
                # Extract key main force control metrics
                close_price = latest_data.get("CLOSE_PRICE", 0)
                change_rate = latest_data.get("CHANGE_RATE", 0)
                turnover_rate = latest_data.get("TURNOVERRATE", 0)
                pe_ratio = latest_data.get("PE_DYNAMIC", 0)
                participate_ratio = latest_data.get("ORG_PARTICIPATE", 0)
                participate_type_cn = latest_data.get("PARTICIPATE_TYPE_CN", "未知")
                prime_inflow = latest_data.get("PRIME_INFLOW", 0)  # 主力净流入
                superdeal_inflow = latest_data.get("SUPERDEAL_INFLOW", 0)  # 超大单流入
                prime_cost = latest_data.get("PRIME_COST", 0)  # 主力成本
                trade_date = latest_data.get("TRADE_DATE", "")
                
                summary["key_metrics"] = {
                    "stock_name": stock_name,
                    "close_price": close_price,
                    "change_rate": change_rate,
                    "turnover_rate": turnover_rate,
                    "pe_ratio": pe_ratio,
                    "trade_date": trade_date
                }
                
                summary["control_indicators"] = {
                    "participate_ratio": participate_ratio,
                    "participate_type": participate_type_cn,
                    "control_strength": self._assess_control_strength(participate_ratio, participate_type_cn)
                }
                
                summary["flow_indicators"] = {
                    "prime_inflow": prime_inflow,
                    "superdeal_inflow": superdeal_inflow,
                    "flow_strength": self._assess_flow_strength(prime_inflow, superdeal_inflow)
                }
                
                summary["cost_indicators"] = {
                    "prime_cost": prime_cost,
                    "current_price": close_price,
                    "cost_position": self._assess_cost_position(prime_cost, close_price)
                }
                
                # Calculate institutional participation score
                institutional_score = 0
                if participate_ratio > 0.5:  # Very high participation
                    institutional_score = 90
                elif participate_ratio > 0.4:  # High participation
                    institutional_score = 75
                elif participate_ratio > 0.3:  # Medium participation
                    institutional_score = 60
                elif participate_ratio > 0.2:  # Low participation
                    institutional_score = 40
                else:  # Very low participation
                    institutional_score = 20
                
                summary["institutional_participation_score"] = institutional_score
                
                # Calculate control type score
                control_type_score = 0
                if "完全控盘" in participate_type_cn:
                    control_type_score = 90
                elif "中度控盘" in participate_type_cn:
                    control_type_score = 70
                elif "轻度控盘" in participate_type_cn:
                    control_type_score = 50
                elif "无控盘" in participate_type_cn:
                    control_type_score = 20
                else:
                    control_type_score = 30
                
                summary["control_type_score"] = control_type_score
                
                # Calculate main force flow score
                flow_score = 0
                if prime_inflow > 0:
                    if prime_inflow > 50000000:  # > 5000万
                        flow_score = 90
                    elif prime_inflow > 20000000:  # > 2000万
                        flow_score = 75
                    elif prime_inflow > 5000000:  # > 500万
                        flow_score = 60
                    else:
                        flow_score = 45
                else:
                    if prime_inflow < -50000000:  # < -5000万
                        flow_score = 10
                    elif prime_inflow < -20000000:  # < -2000万
                        flow_score = 25
                    elif prime_inflow < -5000000:  # < -500万
                        flow_score = 35
                    else:
                        flow_score = 40
                
                summary["main_force_flow_score"] = flow_score
                
                # Calculate cost analysis score
                cost_score = 0
                if prime_cost > 0 and close_price > 0:
                    cost_ratio = close_price / prime_cost
                    if cost_ratio > 1.2:  # Current price 20% above cost
                        cost_score = 85
                    elif cost_ratio > 1.1:  # Current price 10% above cost
                        cost_score = 75
                    elif cost_ratio > 1.0:  # Current price above cost
                        cost_score = 65
                    elif cost_ratio > 0.9:  # Current price close to cost
                        cost_score = 50
                    elif cost_ratio > 0.8:  # Current price 10% below cost
                        cost_score = 35
                    else:  # Current price significantly below cost
                        cost_score = 20
                else:
                    cost_score = 50  # Neutral if no cost data
                
                summary["cost_analysis_score"] = cost_score
                
                # Calculate performance score based on recent change
                performance_score = 0
                if change_rate > 5:  # Strong positive performance
                    performance_score = 90
                elif change_rate > 2:  # Good performance
                    performance_score = 75
                elif change_rate > 0:  # Positive performance
                    performance_score = 65
                elif change_rate > -2:  # Slight negative
                    performance_score = 50
                elif change_rate > -5:  # Moderate negative
                    performance_score = 35
                else:  # Strong negative
                    performance_score = 20
                
                summary["performance_score"] = performance_score
                
                # Generate analysis insights
                summary["analysis"].append(f"{stock_name} 主力控盘分析:")
                summary["analysis"].append(f"机构参与度: {participate_ratio:.2%} ({participate_type_cn})")
                summary["analysis"].append(f"主力净流入: {prime_inflow/10000:.2f}万元")
                summary["analysis"].append(f"超大单流入: {superdeal_inflow/10000:.2f}万元")
                summary["analysis"].append(f"主力成本: ¥{prime_cost:.2f}")
                summary["analysis"].append(f"当前价格: ¥{close_price:.2f}")
                summary["analysis"].append(f"涨跌幅: {change_rate:.2f}%")
                tr_display = turnover_rate if abs(turnover_rate) > 1 else turnover_rate * 100
                summary["analysis"].append(f"换手率: {tr_display:.2f}%")
                
                # Risk assessment
                risk_factors = []
                risk_score = 50  # Start with neutral risk
                
                if participate_ratio < 0.2:
                    risk_factors.append("机构参与度较低")
                    risk_score += 20
                if prime_inflow < 0:
                    risk_factors.append("主力资金流出")
                    risk_score += 15
                if abs(change_rate) > 5:
                    risk_factors.append("股价波动较大")
                    risk_score += 10
                if turnover_rate > 0.1:
                    risk_factors.append("换手率较高")
                    risk_score += 5
                
                summary["risk_assessment"] = {
                    "risk_score": min(risk_score, 100),
                    "risk_factors": risk_factors,
                    "risk_level": "高" if risk_score > 70 else "中" if risk_score > 40 else "低"
                }
                
            else:
                summary["analysis"].append("主力控盘数据为空")
        else:
            summary["analysis"].append("主力控盘数据获取失败")
        
        # Analyze industry position
        if industry_top_data and "error" not in industry_top_data and industry_top_data.get("result"):
            result_data = industry_top_data["result"]
            if result_data and "data" in result_data and result_data["data"]:
                industry_stocks = result_data["data"]
                summary["industry_position"] = {
                    "industry_stocks": len(industry_stocks),
                    "top_performers": [
                        {
                            "name": stock.get("SECURITY_NAME_ABBR", "Unknown"),
                            "code": stock.get("SECURITY_CODE", "Unknown"),
                            "score": stock.get("COMPRE_SCORE", 0),
                            "rank": stock.get("INDUSTRY_RANK", 0)
                        } for stock in industry_stocks[:3]
                    ]
                }
                summary["analysis"].append(f"行业对比: 共{result_data.get('count', 0)}只股票")
            else:
                summary["analysis"].append("行业对比数据为空")
        else:
            summary["analysis"].append("行业对比数据获取失败")
        
        # Calculate overall control score
        valid_scores = [
            s for s in [
                summary["institutional_participation_score"], 
                summary["main_force_flow_score"], 
                summary["control_type_score"],
                summary["cost_analysis_score"], 
                summary["performance_score"]
            ] if s > 0
        ]
        if valid_scores:
            summary["overall_control_score"] = sum(valid_scores) / len(valid_scores)
        
        # Generate recommendation
        if summary["overall_control_score"] >= 75:
            summary["recommendation"] = "strong_positive"
        elif summary["overall_control_score"] >= 60:
            summary["recommendation"] = "positive"
        elif summary["overall_control_score"] >= 40:
            summary["recommendation"] = "neutral"
        else:
            summary["recommendation"] = "negative"
        
        return summary
    
    def _assess_control_strength(self, participate_ratio: float, participate_type: str) -> str:
        """Assess the strength of main force control"""
        if participate_ratio > 0.4 and "完全控盘" in participate_type:
            return "强势控盘"
        elif participate_ratio > 0.3 and ("完全控盘" in participate_type or "中度控盘" in participate_type):
            return "中等控盘"
        elif participate_ratio > 0.2:
            return "轻度控盘"
        else:
            return "控盘较弱"
    
    def _assess_flow_strength(self, prime_inflow: float, superdeal_inflow: float) -> str:
        """Assess the strength of main force flow"""
        total_flow = prime_inflow + superdeal_inflow
        if total_flow > 30000000:  # > 3000万
            return "强势流入"
        elif total_flow > 10000000:  # > 1000万
            return "明显流入"
        elif total_flow > 0:
            return "小幅流入"
        elif total_flow > -10000000:  # > -1000万
            return "小幅流出"
        elif total_flow > -30000000:  # > -3000万
            return "明显流出"
        else:
            return "强势流出"
    
    def _assess_cost_position(self, prime_cost: float, current_price: float) -> str:
        """Assess the cost position relative to current price"""
        if prime_cost <= 0 or current_price <= 0:
            return "数据不足"
        
        ratio = current_price / prime_cost
        if ratio > 1.15:
            return "大幅盈利"
        elif ratio > 1.05:
            return "小幅盈利"
        elif ratio > 0.95:
            return "成本附近"
        elif ratio > 0.85:
            return "小幅亏损"
        else:
            return "大幅亏损"
    
    def run_module_3(self, stock_code: str = "002230") -> Dict:
        """
        Module 3: 舆情监控 (Public Opinion Monitoring)
        监控股票相关的舆情信息，包括声音、公告、研报等多维度舆情分析
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 3: 舆情监控 (Public Opinion Monitoring) for stock {stock_code}")
            
            # Get stock voice/list data
            voice_data = self.api.get_stock_voice_list(stock_code, 20)
            
            # Get stock announcements data
            announcements_data = self.api.get_stock_announcements(stock_code, 20)
            
            # Get stock research reports data
            reports_data = self.api.get_stock_reports(stock_code, 25)
            
            # Process and analyze the public opinion data
            opinion_analysis = {
                "voice_analysis": voice_data,
                "announcements_analysis": announcements_data,
                "reports_analysis": reports_data,
                "opinion_summary": self._generate_opinion_summary(
                    voice_data, announcements_data, reports_data
                )
            }
            
            # Check for errors
            data_sources = [voice_data, announcements_data, reports_data]
            has_errors = any(data.get("error") for data in data_sources)
            successful_sources = sum(1 for data in data_sources if not data.get("error"))
            
            result = {
                "module": "舆情监控 (Public Opinion Monitoring)",
                "stock_code": stock_code,
                "timestamp": datetime.now().isoformat(),
                "data": opinion_analysis,
                "status": "success" if not has_errors else "partial_success" if successful_sources > 0 else "error",
                "data_sources_available": successful_sources,
                "total_data_sources": len(data_sources)
            }
            
            return result
        
        return self._run_module_with_cache(stock_code, 3, _fetch_data)
    
    def _generate_opinion_summary(self, voice_data: Dict, announcements_data: Dict = None,
                                reports_data: Dict = None) -> Dict:
        """Generate public opinion analysis summary"""
        summary = {
            "overall_sentiment_score": 0,
            "voice_sentiment_score": 0,
            "announcements_sentiment_score": 0,
            "reports_sentiment_score": 0,
            "media_coverage_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "voice_metrics": {},
            "announcements_metrics": {},
            "reports_metrics": {},
            "sentiment_breakdown": {},
            "risk_factors": []
        }
        
        # Analyze voice data
        if voice_data and not voice_data.get("error"):
            voice_analysis = self._analyze_voice_sentiment(voice_data)
            summary["voice_sentiment_score"] = voice_analysis["sentiment_score"]
            summary["voice_metrics"] = voice_analysis["metrics"]
            summary["analysis"].extend(voice_analysis["insights"])
        else:
            summary["analysis"].append("声音数据获取失败")
        
        # Analyze announcements data
        if announcements_data and not announcements_data.get("error"):
            announcements_analysis = self._analyze_announcements_sentiment(announcements_data)
            summary["announcements_sentiment_score"] = announcements_analysis["sentiment_score"]
            summary["announcements_metrics"] = announcements_analysis["metrics"]
            summary["analysis"].extend(announcements_analysis["insights"])
        else:
            summary["analysis"].append("公告数据获取失败")
        
        # Analyze reports data
        if reports_data and not reports_data.get("error"):
            reports_analysis = self._analyze_reports_sentiment(reports_data)
            summary["reports_sentiment_score"] = reports_analysis["sentiment_score"]
            summary["reports_metrics"] = reports_analysis["metrics"]
            summary["analysis"].extend(reports_analysis["insights"])
        else:
            summary["analysis"].append("研报数据获取失败")
        
        # Calculate media coverage score
        coverage_score = 0
        total_items = 0
        
        if summary["voice_metrics"].get("total_voices", 0) > 0:
            coverage_score += min(summary["voice_metrics"]["total_voices"] * 2, 50)
            total_items += 1
        
        if summary["announcements_metrics"].get("total_announcements", 0) > 0:
            coverage_score += min(summary["announcements_metrics"]["total_announcements"] * 1.5, 30)
            total_items += 1
        
        if summary["reports_metrics"].get("total_reports", 0) > 0:
            coverage_score += min(summary["reports_metrics"]["total_reports"] * 2, 20)
            total_items += 1
        
        summary["media_coverage_score"] = coverage_score
        
        # Calculate overall sentiment score
        valid_scores = [
            s for s in [
                summary["voice_sentiment_score"], 
                summary["announcements_sentiment_score"], 
                summary["reports_sentiment_score"]
            ] if s > 0
        ]
        
        if valid_scores:
            summary["overall_sentiment_score"] = sum(valid_scores) / len(valid_scores)
        
        # Generate sentiment breakdown
        summary["sentiment_breakdown"] = {
            "voice_sentiment": self._get_sentiment_label(summary["voice_sentiment_score"]),
            "announcements_sentiment": self._get_sentiment_label(summary["announcements_sentiment_score"]),
            "reports_sentiment": self._get_sentiment_label(summary["reports_sentiment_score"]),
            "overall_sentiment": self._get_sentiment_label(summary["overall_sentiment_score"])
        }
        
        # Identify risk factors
        risk_factors = []
        if summary["overall_sentiment_score"] < 30:
            risk_factors.append("舆情整体偏向负面")
        if summary["voice_sentiment_score"] < 20:
            risk_factors.append("声音舆情极度负面")
        if summary["announcements_metrics"].get("negative_announcements", 0) > 5:
            risk_factors.append("负面公告较多")
        if summary["media_coverage_score"] < 10:
            risk_factors.append("媒体关注度较低")
        
        summary["risk_factors"] = risk_factors
        
        # Generate recommendation
        if summary["overall_sentiment_score"] >= 70:
            summary["recommendation"] = "positive"
        elif summary["overall_sentiment_score"] >= 40:
            summary["recommendation"] = "neutral"
        else:
            summary["recommendation"] = "negative"
        
        return summary
    
    def _extract_api_list(self, payload: Dict) -> List[Dict]:
        """Extract list items from East Money API response wrappers."""
        if not payload or payload.get("error"):
            return []
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list") or data.get("items") or []
        return []

    def _analyze_voice_sentiment(self, voice_data: Dict) -> Dict:
        """Analyze voice sentiment data"""
        analysis = {
            "sentiment_score": 50,  # Default neutral
            "metrics": {
                "total_voices": 0,
                "positive_voices": 0,
                "negative_voices": 0,
                "neutral_voices": 0
            },
            "insights": []
        }
        
        try:
            voices = self._extract_api_list(voice_data)
            if voices:
                analysis["metrics"]["total_voices"] = len(voices)
                
                positive_count = 0
                negative_count = 0
                neutral_count = 0
                
                for voice in voices:
                    content = " ".join(filter(None, [
                        voice.get("Art_Title"),
                        voice.get("title"),
                        voice.get("content"),
                        voice.get("summary"),
                    ]))
                    sentiment = self._analyze_text_sentiment(content)
                    
                    if sentiment == "positive":
                        positive_count += 1
                    elif sentiment == "negative":
                        negative_count += 1
                    else:
                        neutral_count += 1
                
                analysis["metrics"]["positive_voices"] = positive_count
                analysis["metrics"]["negative_voices"] = negative_count
                analysis["metrics"]["neutral_voices"] = neutral_count
                
                # Calculate sentiment score
                total = positive_count + negative_count + neutral_count
                if total > 0:
                    sentiment_score = (positive_count * 100 + neutral_count * 50) / total
                    analysis["sentiment_score"] = sentiment_score
                
                analysis["insights"].append(f"声音总数: {total}")
                analysis["insights"].append(f"正面声音: {positive_count}")
                analysis["insights"].append(f"负面声音: {negative_count}")
                analysis["insights"].append(f"中性声音: {neutral_count}")
                analysis["insights"].append(f"声音情感评分: {analysis['sentiment_score']:.1f}/100")
            else:
                analysis["insights"].append("声音数据为空")
        except Exception as e:
            analysis["insights"].append(f"声音数据分析失败: {e}")
        
        return analysis
    
    def _analyze_announcements_sentiment(self, announcements_data: Dict) -> Dict:
        """Analyze announcements sentiment data"""
        analysis = {
            "sentiment_score": 50,  # Default neutral
            "metrics": {
                "total_announcements": 0,
                "positive_announcements": 0,
                "negative_announcements": 0,
                "neutral_announcements": 0
            },
            "insights": []
        }
        
        try:
            announcements = self._extract_api_list(announcements_data)
            if announcements:
                analysis["metrics"]["total_announcements"] = len(announcements)
                
                positive_count = 0
                negative_count = 0
                neutral_count = 0
                
                for announcement in announcements:
                    title = announcement.get("title", "")
                    sentiment = self._analyze_announcement_sentiment(title)
                    
                    if sentiment == "positive":
                        positive_count += 1
                    elif sentiment == "negative":
                        negative_count += 1
                    else:
                        neutral_count += 1
                
                analysis["metrics"]["positive_announcements"] = positive_count
                analysis["metrics"]["negative_announcements"] = negative_count
                analysis["metrics"]["neutral_announcements"] = neutral_count
                
                # Calculate sentiment score
                total = positive_count + negative_count + neutral_count
                if total > 0:
                    sentiment_score = (positive_count * 100 + neutral_count * 50) / total
                    analysis["sentiment_score"] = sentiment_score
                
                analysis["insights"].append(f"公告总数: {total}")
                analysis["insights"].append(f"正面公告: {positive_count}")
                analysis["insights"].append(f"负面公告: {negative_count}")
                analysis["insights"].append(f"中性公告: {neutral_count}")
                analysis["insights"].append(f"公告情感评分: {analysis['sentiment_score']:.1f}/100")
            else:
                analysis["insights"].append("公告数据为空")
        except Exception as e:
            analysis["insights"].append(f"公告数据分析失败: {e}")
        
        return analysis
    
    def _analyze_reports_sentiment(self, reports_data: Dict) -> Dict:
        """Analyze research reports sentiment data"""
        analysis = {
            "sentiment_score": 50,  # Default neutral
            "metrics": {
                "total_reports": 0,
                "positive_reports": 0,
                "negative_reports": 0,
                "neutral_reports": 0,
                "average_rating": 0
            },
            "insights": []
        }
        
        try:
            reports = self._extract_api_list(reports_data)
            if reports:
                analysis["metrics"]["total_reports"] = len(reports)
                
                positive_count = 0
                negative_count = 0
                neutral_count = 0
                total_rating = 0
                rating_count = 0
                
                for report in reports:
                    title = report.get("title", "")
                    rating = report.get("rating") or report.get("emRatingName") or report.get("sRatingName") or ""
                    
                    sentiment = self._analyze_report_sentiment(title, rating)
                    
                    if sentiment == "positive":
                        positive_count += 1
                    elif sentiment == "negative":
                        negative_count += 1
                    else:
                        neutral_count += 1
                    
                    # Analyze rating
                    if rating:
                        rating_score = self._parse_rating(rating)
                        if rating_score > 0:
                            total_rating += rating_score
                            rating_count += 1
                
                analysis["metrics"]["positive_reports"] = positive_count
                analysis["metrics"]["negative_reports"] = negative_count
                analysis["metrics"]["neutral_reports"] = neutral_count
                
                if rating_count > 0:
                    analysis["metrics"]["average_rating"] = total_rating / rating_count
                
                # Calculate sentiment score
                total = positive_count + negative_count + neutral_count
                if total > 0:
                    sentiment_score = (positive_count * 100 + neutral_count * 50) / total
                    analysis["sentiment_score"] = sentiment_score
                
                analysis["insights"].append(f"研报总数: {total}")
                analysis["insights"].append(f"正面研报: {positive_count}")
                analysis["insights"].append(f"负面研报: {negative_count}")
                analysis["insights"].append(f"中性研报: {neutral_count}")
                analysis["insights"].append(f"研报情感评分: {analysis['sentiment_score']:.1f}/100")
                if rating_count > 0:
                    analysis["insights"].append(f"平均评级: {analysis['metrics']['average_rating']:.1f}")
            else:
                analysis["insights"].append("研报数据为空")
        except Exception as e:
            analysis["insights"].append(f"研报数据分析失败: {e}")
        
        return analysis
    
    def _analyze_text_sentiment(self, text: str) -> str:
        """Simple text sentiment analysis"""
        if not text:
            return "neutral"
        
        text = text.lower()
        
        # Positive keywords
        positive_keywords = ["涨", "好", "优", "强", "买入", "推荐", "看好", "增长", "盈利", "利好", "突破"]
        # Negative keywords
        negative_keywords = ["跌", "坏", "差", "弱", "卖出", "看空", "亏损", "利空", "风险", "下跌", "破位"]
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in text)
        negative_count = sum(1 for keyword in negative_keywords if keyword in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _analyze_announcement_sentiment(self, title: str) -> str:
        """Analyze announcement sentiment based on title"""
        if not title:
            return "neutral"
        
        title = title.lower()
        
        # Positive announcement keywords
        positive_keywords = ["盈利", "增长", "收购", "投资", "合作", "中标", "扩张", "分红", "增持"]
        # Negative announcement keywords
        negative_keywords = ["亏损", "减持", "风险", "警示", "处罚", "调查", "暂停", "终止", "取消"]
        
        positive_count = sum(1 for keyword in positive_keywords if keyword in title)
        negative_count = sum(1 for keyword in negative_keywords if keyword in title)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _analyze_report_sentiment(self, title: str, rating: str) -> str:
        """Analyze report sentiment based on title and rating"""
        sentiment = self._analyze_text_sentiment(title)
        
        # Adjust based on rating
        if rating:
            rating_score = self._parse_rating(rating)
            if rating_score >= 4:
                return "positive"
            elif rating_score <= 2:
                return "negative"
        
        return sentiment
    
    def _parse_rating(self, rating: str) -> float:
        """Parse rating string to numeric score"""
        if not rating:
            return 0
        
        rating = rating.upper()
        
        # Rating mapping
        rating_map = {
            "买入": 5, "强烈推荐": 5, "推荐": 4, "增持": 4,
            "中性": 3, "持有": 3, "观望": 3,
            "减持": 2, "卖出": 1, "回避": 1
        }
        
        for key, value in rating_map.items():
            if key in rating:
                return value
        
        return 3  # Default neutral
    
    def _get_sentiment_label(self, score: float) -> str:
        """Get sentiment label from score"""
        if score >= 70:
            return "正面"
        elif score >= 40:
            return "中性"
        else:
            return "负面"
    
    def run_module_4(self, stock_code: str = "002916") -> Dict:
        """
        Module 4: 市场参与意愿 (Market Participation Willingness)
        分析市场参与意愿相关指标，包括用户关注度、市场参与意愿变化、五日平均参与意愿等
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 4: 市场参与意愿 (Market Participation Willingness) for stock {stock_code}")
            
            # Get market participation data
            participation_data = self.api.get_stock_participation(stock_code)
            
            # Get market focus data
            market_focus_data = self.api.get_stock_market_focus(stock_code)
            
            # Get stock comments data for additional context
            comments_data = self.api.get_stock_comments_data(stock_code)
            
            # Generate market participation analysis summary
            summary = self._generate_market_participation_summary(
                participation_data, market_focus_data, comments_data
            )
            
            result = {
                "module": "市场参与意愿",
                "stock_code": stock_code,
                "status": "completed",
                "data_sources_available": 0,
                "total_data_sources": 3,
                "summary": summary,
                "raw_data": {
                    "participation_data": participation_data,
                    "market_focus_data": market_focus_data,
                    "comments_data": comments_data
                }
            }
            
            # Count available data sources
            if "error" not in participation_data:
                result["data_sources_available"] += 1
            if "error" not in market_focus_data:
                result["data_sources_available"] += 1
            if "error" not in comments_data:
                result["data_sources_available"] += 1
                
            logger.info(f"Module 4 completed with {result['data_sources_available']}/{result['total_data_sources']} data sources")
            return result
        
        return self._run_module_with_cache(stock_code, 4, _fetch_data)
    
    def _generate_market_participation_summary(self, participation_data: Dict, 
                                             market_focus_data: Dict = None,
                                             comments_data: Dict = None) -> Dict:
        """Generate market participation analysis summary"""
        summary = {
            "overall_participation_score": 0,
            "market_focus_score": 0,
            "participation_willingness_score": 0,
            "five_day_average_score": 0,
            "trend_analysis_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "participation_metrics": {},
            "focus_metrics": {},
            "comments_metrics": {},
            "trend_indicators": {},
            "risk_factors": []
        }
        
        # Analyze participation data
        if "error" not in participation_data and participation_data.get("result", {}).get("data"):
            participation_list = participation_data["result"]["data"]
            if participation_list:
                latest_data = participation_list[0]
                
                # Extract key metrics
                participation_wish_change = float(latest_data.get("PARTICIPATION_WISH_CHANGE", 0))
                participation_wish_5days_change = float(latest_data.get("PARTICIPATION_WISH_5DAYSCHANGE", 0))
                trade_date = latest_data.get("TRADE_DATE", "")
                
                summary["participation_metrics"] = {
                    "participation_wish_change": participation_wish_change,
                    "participation_wish_5days_change": participation_wish_5days_change,
                    "trade_date": trade_date
                }
                
                # Score participation willingness (0-100)
                if participation_wish_change > 5:
                    participation_score = 90
                    summary["analysis"].append("市场参与意愿大幅增强，投资者情绪积极")
                elif participation_wish_change > 2:
                    participation_score = 75
                    summary["analysis"].append("市场参与意愿明显增强，投资者信心提升")
                elif participation_wish_change > 0:
                    participation_score = 65
                    summary["analysis"].append("市场参与意愿有所增强，投资者情绪向好")
                elif participation_wish_change > -2:
                    participation_score = 50
                    summary["analysis"].append("市场参与意愿基本稳定，投资者情绪中性")
                elif participation_wish_change > -5:
                    participation_score = 35
                    summary["analysis"].append("市场参与意愿有所减弱，投资者情绪谨慎")
                else:
                    participation_score = 20
                    summary["analysis"].append("市场参与意愿大幅减弱，投资者情绪悲观")
                
                summary["participation_willingness_score"] = participation_score
                
                # Score 5-day average (0-100)
                if participation_wish_5days_change > 3:
                    avg_score = 85
                    summary["analysis"].append("五日平均参与意愿持续增强，趋势向好")
                elif participation_wish_5days_change > 1:
                    avg_score = 70
                    summary["analysis"].append("五日平均参与意愿稳步提升")
                elif participation_wish_5days_change > -1:
                    avg_score = 55
                    summary["analysis"].append("五日平均参与意愿相对稳定")
                elif participation_wish_5days_change > -3:
                    avg_score = 40
                    summary["analysis"].append("五日平均参与意愿有所下降")
                else:
                    avg_score = 25
                    summary["analysis"].append("五日平均参与意愿持续下降，需要关注")
                
                summary["five_day_average_score"] = avg_score
                
                # Risk factors
                if participation_wish_change < -3:
                    summary["risk_factors"].append("当日参与意愿大幅下降")
                if participation_wish_5days_change < -2:
                    summary["risk_factors"].append("五日平均参与意愿持续下降")
            else:
                summary["analysis"].append("暂无市场参与意愿数据")
        else:
            summary["analysis"].append("无法获取市场参与意愿数据")
        
        # Analyze market focus data
        if market_focus_data and "error" not in market_focus_data and market_focus_data.get("result") and market_focus_data.get("result", {}).get("data"):
            focus_list = market_focus_data["result"]["data"]
            if focus_list:
                latest_focus = focus_list[0]
                
                market_focus = float(latest_focus.get("MARKET_FOCUS", 0))
                market_focus_change = float(latest_focus.get("MARKET_FOCUS_CHANGE", 0))
                market_focus_rank = latest_focus.get("MARKET_FOCUS_RANK", "N/A")
                total_market = latest_focus.get("TOTAL_MARKET", "N/A")
                
                summary["focus_metrics"] = {
                    "market_focus": market_focus,
                    "market_focus_change": market_focus_change,
                    "market_focus_rank": market_focus_rank,
                    "total_market": total_market
                }
                
                # Score market focus (0-100)
                if market_focus > 80:
                    focus_score = 90
                    summary["analysis"].append(f"市场关注度很高({market_focus:.2f})，排名第{market_focus_rank}位")
                elif market_focus > 60:
                    focus_score = 75
                    summary["analysis"].append(f"市场关注度较高({market_focus:.2f})，排名第{market_focus_rank}位")
                elif market_focus > 40:
                    focus_score = 60
                    summary["analysis"].append(f"市场关注度中等({market_focus:.2f})，排名第{market_focus_rank}位")
                elif market_focus > 20:
                    focus_score = 45
                    summary["analysis"].append(f"市场关注度较低({market_focus:.2f})，排名第{market_focus_rank}位")
                else:
                    focus_score = 25
                    summary["analysis"].append(f"市场关注度很低({market_focus:.2f})，排名第{market_focus_rank}位")
                
                summary["market_focus_score"] = focus_score
                
                # Risk factors
                if market_focus < 30:
                    summary["risk_factors"].append("市场关注度较低")
                if market_focus_change < -10:
                    summary["risk_factors"].append("市场关注度大幅下降")
            else:
                summary["analysis"].append("暂无市场关注度数据")
        else:
            summary["analysis"].append("无法获取市场关注度数据")
        
        # Analyze comments data
        if comments_data and "error" not in comments_data and comments_data.get("result") and comments_data.get("result", {}).get("data"):
            comments_list = comments_data["result"]["data"]
            if comments_list:
                latest_comment = comments_list[0]
                update_date = latest_comment.get("UPDATE_DATE", "")
                
                summary["comments_metrics"] = {
                    "update_date": update_date,
                    "data_availability": True
                }
                summary["analysis"].append(f"评论数据更新至: {update_date}")
            else:
                summary["analysis"].append("暂无评论数据")
        else:
            summary["analysis"].append("无法获取评论数据")
        
        # Calculate overall participation score
        scores = [
            summary["participation_willingness_score"],
            summary["five_day_average_score"],
            summary["market_focus_score"]
        ]
        valid_scores = [s for s in scores if s > 0]
        
        if valid_scores:
            summary["overall_participation_score"] = sum(valid_scores) / len(valid_scores)
        else:
            summary["overall_participation_score"] = 0
        
        # Generate recommendation
        if summary["overall_participation_score"] >= 75:
            summary["recommendation"] = "积极"
            summary["analysis"].append("市场参与意愿整体积极，建议关注")
        elif summary["overall_participation_score"] >= 60:
            summary["recommendation"] = "乐观"
            summary["analysis"].append("市场参与意愿较为乐观，可适当关注")
        elif summary["overall_participation_score"] >= 40:
            summary["recommendation"] = "中性"
            summary["analysis"].append("市场参与意愿中性，保持观望")
        elif summary["overall_participation_score"] >= 25:
            summary["recommendation"] = "谨慎"
            summary["analysis"].append("市场参与意愿较弱，建议谨慎")
        else:
            summary["recommendation"] = "悲观"
            summary["analysis"].append("市场参与意愿悲观，建议回避")
        
        # Trend analysis
        if summary["participation_metrics"] and summary["focus_metrics"]:
            participation_trend = summary["participation_metrics"].get("participation_wish_change", 0)
            focus_trend = summary["focus_metrics"].get("market_focus_change", 0)
            
            if participation_trend > 0 and focus_trend > 0:
                summary["trend_indicators"]["trend"] = "上升"
                summary["trend_analysis_score"] = 80
                summary["analysis"].append("参与意愿和关注度均呈上升趋势")
            elif participation_trend < 0 and focus_trend < 0:
                summary["trend_indicators"]["trend"] = "下降"
                summary["trend_analysis_score"] = 20
                summary["analysis"].append("参与意愿和关注度均呈下降趋势")
            else:
                summary["trend_indicators"]["trend"] = "分化"
                summary["trend_analysis_score"] = 50
                summary["analysis"].append("参与意愿和关注度趋势分化")
        
        return summary
    
    def run_module_5(self, stock_code: str = "002916") -> Dict:
        """
        Module 5: 趋势研判 (Trend Analysis)
        分析股票价格趋势和成交量趋势，提供趋势判断和投资建议
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 5: 趋势研判 (Trend Analysis) for stock {stock_code}")
            
            # Get trend volume comment data
            trend_comment_data = self.api.get_stock_trend_comment(stock_code)
            
            # Get stock trend volume data
            trend_volume_data = self.api.get_stock_trend_volume_data(stock_code)
            
            # Get stock price trend data for additional context
            price_trend_data = self.api.get_stock_price_trend(stock_code)
            
            # Generate trend analysis summary
            summary = self._generate_trend_analysis_summary(
                trend_comment_data, trend_volume_data, price_trend_data
            )
            
            result = {
                "module": "趋势研判",
                "stock_code": stock_code,
                "status": "completed",
                "data_sources_available": 0,
                "total_data_sources": 3,
                "summary": summary,
                "raw_data": {
                    "trend_comment_data": trend_comment_data,
                    "trend_volume_data": trend_volume_data,
                    "price_trend_data": price_trend_data
                }
            }
            
            # Count available data sources
            if "error" not in trend_comment_data:
                result["data_sources_available"] += 1
            if "error" not in trend_volume_data:
                result["data_sources_available"] += 1
            if "error" not in price_trend_data:
                result["data_sources_available"] += 1
                
            logger.info(f"Module 5 completed with {result['data_sources_available']}/{result['total_data_sources']} data sources")
            return result
        
        return self._run_module_with_cache(stock_code, 5, _fetch_data)
    
    def _generate_trend_analysis_summary(self, trend_comment_data: Dict, 
                                       trend_volume_data: Dict = None,
                                       price_trend_data: Dict = None) -> Dict:
        """Generate trend analysis summary"""
        summary = {
            "overall_trend_score": 0,
            "trend_comment_score": 0,
            "volume_trend_score": 0,
            "price_trend_score": 0,
            "trend_strength_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "trend_comment_metrics": {},
            "volume_metrics": {},
            "price_metrics": {},
            "trend_indicators": {},
            "risk_factors": []
        }
        
        # Analyze trend comment data
        if "error" not in trend_comment_data and trend_comment_data.get("result") and trend_comment_data.get("result", {}).get("data"):
            comment_list = trend_comment_data["result"]["data"]
            if comment_list:
                latest_comment = comment_list[0]
                
                comment_txt = latest_comment.get("COMMENT_TXT", "")
                trade_date = latest_comment.get("TRADE_DATE", "")
                
                summary["trend_comment_metrics"] = {
                    "comment_txt": comment_txt,
                    "trade_date": trade_date
                }
                
                # Analyze comment sentiment for trend
                if comment_txt:
                    # Simple sentiment analysis based on keywords
                    positive_keywords = ["上涨", "突破", "强势", "看好", "买入", "增长", "反弹", "拉升", "突破", "放量"]
                    negative_keywords = ["下跌", "破位", "弱势", "看空", "卖出", "下降", "回调", "下跌", "缩量", "跌破"]
                    
                    positive_count = sum(1 for keyword in positive_keywords if keyword in comment_txt)
                    negative_count = sum(1 for keyword in negative_keywords if keyword in comment_txt)
                    
                    if positive_count > negative_count:
                        comment_score = 75
                        summary["analysis"].append("趋势评论偏向积极，技术面看好")
                    elif negative_count > positive_count:
                        comment_score = 25
                        summary["analysis"].append("趋势评论偏向消极，技术面看空")
                    else:
                        comment_score = 50
                        summary["analysis"].append("趋势评论中性，技术面观望")
                    
                    summary["trend_comment_score"] = comment_score
                    summary["analysis"].append(f"最新评论: {comment_txt[:50]}...")
                else:
                    summary["analysis"].append("暂无趋势评论数据")
            else:
                summary["analysis"].append("暂无趋势评论数据")
        else:
            summary["analysis"].append("无法获取趋势评论数据")
        
        # Analyze trend volume data
        if trend_volume_data and "error" not in trend_volume_data and trend_volume_data.get("result") and trend_volume_data.get("result", {}).get("data"):
            volume_list = trend_volume_data["result"]["data"]
            if volume_list:
                latest_volume = volume_list[0]
                update_date = latest_volume.get("UPDATE_DATE", "")
                
                summary["volume_metrics"] = {
                    "update_date": update_date,
                    "data_availability": True
                }
                summary["analysis"].append(f"趋势成交量数据更新至: {update_date}")
                
                # Score volume trend (assuming data indicates volume trend)
                summary["volume_trend_score"] = 60  # Default moderate score
                summary["analysis"].append("成交量趋势数据正常")
            else:
                summary["analysis"].append("暂无趋势成交量数据")
        else:
            summary["analysis"].append("无法获取趋势成交量数据")
        
        # Analyze price trend data
        if price_trend_data and "error" not in price_trend_data and price_trend_data.get("result") and price_trend_data.get("result", {}).get("data"):
            price_list = price_trend_data["result"]["data"]
            if price_list:
                latest_price = price_list[0]
                
                # Extract price change information
                change_rate = float(latest_price.get("AVERAGE_1_INCREASE", 0)) * 100  # Convert to percentage
                price = float(latest_price.get("TOTAL_SCORE", 0))  # Use total score as price indicator
                
                summary["price_metrics"] = {
                    "change_rate": change_rate,
                    "price": price
                }
                
                # Score price trend based on change rate
                if change_rate > 5:
                    price_score = 85
                    summary["analysis"].append(f"价格大幅上涨{change_rate:.2f}%，趋势强劲")
                elif change_rate > 2:
                    price_score = 70
                    summary["analysis"].append(f"价格上涨{change_rate:.2f}%，趋势向好")
                elif change_rate > 0:
                    price_score = 60
                    summary["analysis"].append(f"价格小幅上涨{change_rate:.2f}%，趋势温和")
                elif change_rate > -2:
                    price_score = 50
                    summary["analysis"].append(f"价格基本稳定({change_rate:.2f}%)，趋势中性")
                elif change_rate > -5:
                    price_score = 35
                    summary["analysis"].append(f"价格下跌{abs(change_rate):.2f}%，趋势偏弱")
                else:
                    price_score = 20
                    summary["analysis"].append(f"价格大幅下跌{abs(change_rate):.2f}%，趋势疲弱")
                
                summary["price_trend_score"] = price_score
                
                # Risk factors
                if change_rate < -3:
                    summary["risk_factors"].append("价格大幅下跌")
            else:
                summary["analysis"].append("暂无价格趋势数据")
        else:
            summary["analysis"].append("无法获取价格趋势数据")
        
        # Calculate trend strength based on available data
        scores = [
            summary["trend_comment_score"],
            summary["volume_trend_score"],
            summary["price_trend_score"]
        ]
        valid_scores = [s for s in scores if s > 0]
        
        if valid_scores:
            summary["trend_strength_score"] = sum(valid_scores) / len(valid_scores)
        else:
            summary["trend_strength_score"] = 0
        
        # Calculate overall trend score
        summary["overall_trend_score"] = summary["trend_strength_score"]
        
        # Generate recommendation based on trend analysis
        if summary["overall_trend_score"] >= 75:
            summary["recommendation"] = "强势上涨"
            summary["analysis"].append("技术面强势，建议关注买入机会")
        elif summary["overall_trend_score"] >= 65:
            summary["recommendation"] = "温和上涨"
            summary["analysis"].append("技术面向好，可适当关注")
        elif summary["overall_trend_score"] >= 45:
            summary["recommendation"] = "震荡整理"
            summary["analysis"].append("技术面中性，建议观望")
        elif summary["overall_trend_score"] >= 30:
            summary["recommendation"] = "偏弱调整"
            summary["analysis"].append("技术面偏弱，建议谨慎")
        else:
            summary["recommendation"] = "弱势下跌"
            summary["analysis"].append("技术面疲弱，建议回避")
        
        # Trend indicators
        if summary["price_metrics"] and summary["trend_comment_score"] > 0:
            price_change = summary["price_metrics"].get("change_rate", 0)
            comment_score = summary["trend_comment_score"]
            
            if price_change > 0 and comment_score > 60:
                summary["trend_indicators"]["trend"] = "上升"
                summary["trend_indicators"]["strength"] = "强"
            elif price_change > 0 and comment_score > 40:
                summary["trend_indicators"]["trend"] = "上升"
                summary["trend_indicators"]["strength"] = "中等"
            elif price_change < 0 and comment_score < 40:
                summary["trend_indicators"]["trend"] = "下降"
                summary["trend_indicators"]["strength"] = "强"
            elif price_change < 0 and comment_score < 60:
                summary["trend_indicators"]["trend"] = "下降"
                summary["trend_indicators"]["strength"] = "中等"
            else:
                summary["trend_indicators"]["trend"] = "震荡"
                summary["trend_indicators"]["strength"] = "弱"
        
        return summary
    
    def run_module_6(self, stock_code: str = "002916") -> Dict:
        """
        Module 6: 资金动向 (Capital Flow)
        分析资金流入流出情况，包括个股资金动向、行业资金动向、主力资金流向等
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 6: 资金动向 (Capital Flow) for stock {stock_code}")
            
            # Get individual stock capital flow data
            stock_capital_flow = self.api.get_stock_capital_flow(stock_code)
            
            # Get industry capital flow data
            industry_capital_flow = self.api.get_industry_capital_flow(stock_code)
            
            # Get industry ranking data for comparison
            industry_ranking = self.api.get_industry_ranking_data(stock_code)
            
            # Generate capital flow analysis summary
            summary = self._generate_capital_flow_summary(
                stock_capital_flow, industry_capital_flow, industry_ranking
            )
            
            result = {
                "module": "资金动向",
                "stock_code": stock_code,
                "status": "completed",
                "data_sources_available": 0,
                "total_data_sources": 3,
                "summary": summary,
                "raw_data": {
                    "stock_capital_flow": stock_capital_flow,
                    "industry_capital_flow": industry_capital_flow,
                    "industry_ranking": industry_ranking
                }
            }
            
            # Count available data sources
            if "error" not in stock_capital_flow:
                result["data_sources_available"] += 1
            if "error" not in industry_capital_flow:
                result["data_sources_available"] += 1
            if "error" not in industry_ranking:
                result["data_sources_available"] += 1
                
            logger.info(f"Module 6 completed with {result['data_sources_available']}/{result['total_data_sources']} data sources")
            return result
        
        return self._run_module_with_cache(stock_code, 6, _fetch_data)
    
    def _generate_capital_flow_summary(self, stock_capital_flow: Dict, 
                                     industry_capital_flow: Dict = None,
                                     industry_ranking: Dict = None) -> Dict:
        """Generate capital flow analysis summary"""
        summary = {
            "overall_capital_score": 0,
            "stock_flow_score": 0,
            "industry_flow_score": 0,
            "ranking_score": 0,
            "flow_strength_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "stock_flow_metrics": {},
            "industry_flow_metrics": {},
            "ranking_metrics": {},
            "flow_indicators": {},
            "risk_factors": []
        }
        
        # Analyze stock capital flow data
        if "error" not in stock_capital_flow and stock_capital_flow.get("result") and stock_capital_flow.get("result", {}).get("data"):
            flow_list = stock_capital_flow["result"]["data"]
            if flow_list:
                latest_flow = flow_list[0]
                
                # Extract key metrics
                capital_flows = float(latest_flow.get("CAPITAL_FLOWS", 0))
                capital_flows_ratio = float(latest_flow.get("CAPITAL_FLOWS_RATIO", 0))
                capital_flows_5days = float(latest_flow.get("CAPITAL_FLOWS_5DAYS", 0))
                capital_flows_5days_ratio = float(latest_flow.get("CAPITAL_FLOWS_5DAYSRATIO", 0))
                trade_date = latest_flow.get("TRADE_DATE", "")
                
                summary["stock_flow_metrics"] = {
                    "capital_flows": capital_flows,
                    "capital_flows_ratio": capital_flows_ratio,
                    "capital_flows_5days": capital_flows_5days,
                    "capital_flows_5days_ratio": capital_flows_5days_ratio,
                    "trade_date": trade_date
                }
                
                # Score stock capital flow (0-100)
                if capital_flows > 100000000:  # 1亿以上
                    stock_score = 90
                    summary["analysis"].append(f"主力资金大幅流入{capital_flows/100000000:.2f}亿元，资金面强势")
                elif capital_flows > 50000000:  # 5000万以上
                    stock_score = 80
                    summary["analysis"].append(f"主力资金明显流入{capital_flows/100000000:.2f}亿元，资金面向好")
                elif capital_flows > 10000000:  # 1000万以上
                    stock_score = 70
                    summary["analysis"].append(f"主力资金净流入{capital_flows/100000000:.2f}亿元，资金面积极")
                elif capital_flows > 0:
                    stock_score = 60
                    summary["analysis"].append(f"主力资金小幅流入{capital_flows/100000000:.2f}亿元，资金面稳定")
                elif capital_flows > -10000000:  # -1000万以上
                    stock_score = 50
                    summary["analysis"].append(f"主力资金小幅流出{abs(capital_flows)/100000000:.2f}亿元，资金面中性")
                elif capital_flows > -50000000:  # -5000万以上
                    stock_score = 35
                    summary["analysis"].append(f"主力资金明显流出{abs(capital_flows)/100000000:.2f}亿元，资金面偏弱")
                else:
                    stock_score = 20
                    summary["analysis"].append(f"主力资金大幅流出{abs(capital_flows)/100000000:.2f}亿元，资金面疲弱")
                
                summary["stock_flow_score"] = stock_score
                
                # Score 5-day flow trend
                if capital_flows_5days > capital_flows:
                    summary["analysis"].append("五日资金流向优于当日，趋势向好")
                elif capital_flows_5days < capital_flows:
                    summary["analysis"].append("五日资金流向弱于当日，需要关注")
                
                # Risk factors
                if capital_flows < -50000000:
                    summary["risk_factors"].append("主力资金大幅流出")
                if capital_flows_ratio < -2:
                    summary["risk_factors"].append("资金流出占流通市值比例较高")
            else:
                summary["analysis"].append("暂无个股资金流向数据")
        else:
            summary["analysis"].append("无法获取个股资金流向数据")
        
        # Analyze industry capital flow data
        if industry_capital_flow and "error" not in industry_capital_flow and industry_capital_flow.get("result") and industry_capital_flow.get("result", {}).get("data"):
            industry_list = industry_capital_flow["result"]["data"]
            if industry_list:
                latest_industry = industry_list[0]
                
                industry_name = latest_industry.get("BOARD_NAME", "")
                industry_flows = float(latest_industry.get("BOARD_CAPITAL_FLOWS", 0))
                industry_5days_flows = float(latest_industry.get("BOARD_CAPITAL_5FLOWS", 0))
                
                summary["industry_flow_metrics"] = {
                    "industry_name": industry_name,
                    "industry_flows": industry_flows,
                    "industry_5days_flows": industry_5days_flows
                }
                
                # Score industry flow
                if industry_flows > 1000000000:  # 10亿以上
                    industry_score = 85
                    summary["analysis"].append(f"{industry_name}行业资金大幅流入{industry_flows/1000000000:.2f}亿元")
                elif industry_flows > 500000000:  # 5亿以上
                    industry_score = 75
                    summary["analysis"].append(f"{industry_name}行业资金明显流入{industry_flows/1000000000:.2f}亿元")
                elif industry_flows > 0:
                    industry_score = 65
                    summary["analysis"].append(f"{industry_name}行业资金净流入{industry_flows/1000000000:.2f}亿元")
                else:
                    industry_score = 45
                    summary["analysis"].append(f"{industry_name}行业资金净流出{abs(industry_flows)/1000000000:.2f}亿元")
                
                summary["industry_flow_score"] = industry_score
            else:
                summary["analysis"].append("暂无行业资金流向数据")
        else:
            summary["analysis"].append("无法获取行业资金流向数据")
        
        # Analyze industry ranking data
        if industry_ranking and "error" not in industry_ranking and industry_ranking.get("result") and industry_ranking.get("result", {}).get("data"):
            ranking_list = industry_ranking["result"]["data"]
            if ranking_list:
                # Find current stock position in ranking
                current_stock_rank = 0
                for i, item in enumerate(ranking_list):
                    if item.get("SECURITY_CODE") == stock_capital_flow.get("result", {}).get("data", [{}])[0].get("SECURITY_CODE"):
                        current_stock_rank = i + 1
                        break
                
                summary["ranking_metrics"] = {
                    "current_rank": current_stock_rank,
                    "total_stocks": len(ranking_list)
                }
                
                # Score ranking position
                if current_stock_rank == 1:
                    ranking_score = 95
                    summary["analysis"].append("资金流向排名第1位，表现优异")
                elif current_stock_rank <= 3:
                    ranking_score = 85
                    summary["analysis"].append(f"资金流向排名第{current_stock_rank}位，表现良好")
                elif current_stock_rank <= 5:
                    ranking_score = 70
                    summary["analysis"].append(f"资金流向排名第{current_stock_rank}位，表现中等")
                else:
                    ranking_score = 50
                    summary["analysis"].append(f"资金流向排名第{current_stock_rank}位，需要关注")
                
                summary["ranking_score"] = ranking_score
            else:
                summary["analysis"].append("暂无行业排名数据")
        else:
            summary["analysis"].append("无法获取行业排名数据")
        
        # Calculate flow strength based on available data
        scores = [
            summary["stock_flow_score"],
            summary["industry_flow_score"],
            summary["ranking_score"]
        ]
        valid_scores = [s for s in scores if s > 0]
        
        if valid_scores:
            summary["flow_strength_score"] = sum(valid_scores) / len(valid_scores)
        else:
            summary["flow_strength_score"] = 0
        
        # Calculate overall capital score
        summary["overall_capital_score"] = summary["flow_strength_score"]
        
        # Generate recommendation based on capital flow analysis
        if summary["overall_capital_score"] >= 80:
            summary["recommendation"] = "资金强势流入"
            summary["analysis"].append("资金面强势，建议重点关注")
        elif summary["overall_capital_score"] >= 70:
            summary["recommendation"] = "资金积极流入"
            summary["analysis"].append("资金面向好，可适当关注")
        elif summary["overall_capital_score"] >= 50:
            summary["recommendation"] = "资金流向中性"
            summary["analysis"].append("资金面中性，保持观望")
        elif summary["overall_capital_score"] >= 30:
            summary["recommendation"] = "资金偏弱流出"
            summary["analysis"].append("资金面偏弱，建议谨慎")
        else:
            summary["recommendation"] = "资金大幅流出"
            summary["analysis"].append("资金面疲弱，建议回避")
        
        # Flow indicators
        if summary["stock_flow_metrics"] and summary["industry_flow_metrics"]:
            stock_flow = summary["stock_flow_metrics"].get("capital_flows", 0)
            industry_flow = summary["industry_flow_metrics"].get("industry_flows", 0)
            
            if stock_flow > 0 and industry_flow > 0:
                summary["flow_indicators"]["trend"] = "流入"
                summary["flow_indicators"]["strength"] = "强"
                summary["analysis"].append("个股和行业资金均呈流入态势")
            elif stock_flow < 0 and industry_flow < 0:
                summary["flow_indicators"]["trend"] = "流出"
                summary["flow_indicators"]["strength"] = "强"
                summary["analysis"].append("个股和行业资金均呈流出态势")
            else:
                summary["flow_indicators"]["trend"] = "分化"
                summary["flow_indicators"]["strength"] = "中等"
                summary["analysis"].append("个股和行业资金流向分化")
        
        return summary
    
    def run_module_7(self, stock_code: str = "002916") -> Dict:
        """
        Module 7: 财务评估 (Financial Evaluation)
        评估公司财务状况和价值评估
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 7: 财务评估 (Financial Evaluation) for stock {stock_code}")
            
            # Financial signals (commentary) + financial analysis (ratios/rankings)
            financial_signals = self.api.get_financial_evaluation(stock_code)
            financial_analysis = self.api.get_financial_analysis(stock_code)

            summary = self._generate_financial_evaluation_summary(
                financial_signals, financial_analysis
            )

            result = {
                "module": "财务评估",
                "stock_code": stock_code,
                "status": "completed",
                "data_sources_available": 0,
                "total_data_sources": 2,
                "summary": summary,
                "raw_data": {
                    "financial_evaluation": financial_signals,
                    "financial_analysis": financial_analysis,
                }
            }

            if "error" not in financial_signals and self._extract_api_rows(financial_signals):
                result["data_sources_available"] += 1
            if "error" not in financial_analysis and self._extract_api_rows(financial_analysis):
                result["data_sources_available"] += 1
                
            logger.info(f"Module 7 completed with {result['data_sources_available']}/{result['total_data_sources']} data sources")
            return result
        
        return self._run_module_with_cache(stock_code, 7, _fetch_data)
    
    def run_module_8(self, stock_code: str = "002916") -> Dict:
        """
        Module 8: 龙虎榜和融资融券 (Dragon Tiger Board and Margin Trading)
        分析龙虎榜数据和融资融券情况
        """
        def _fetch_data(stock_code):
            logger.info(f"Running Module 8: 龙虎榜和融资融券 (Dragon Tiger Board and Margin Trading) for stock {stock_code}")
            
            # Get dragon tiger board data
            dragon_tiger_data = self.api.get_dragon_tiger_board(stock_code)
            
            # Get margin trading data
            margin_trading_data = self.api.get_margin_trading(stock_code)
            
            # Generate dragon tiger board and margin trading summary
            summary = self._generate_dragon_tiger_margin_summary(
                dragon_tiger_data, margin_trading_data
            )
            
            result = {
                "module": "龙虎榜和融资融券",
                "stock_code": stock_code,
                "status": "completed",
                "data_sources_available": 0,
                "total_data_sources": 2,
                "summary": summary,
                "raw_data": {
                    "dragon_tiger_board": dragon_tiger_data,
                    "margin_trading": margin_trading_data
                }
            }
            
            # Count available data sources
            if "error" not in dragon_tiger_data:
                result["data_sources_available"] += 1
            if "error" not in margin_trading_data:
                result["data_sources_available"] += 1
                
            logger.info(f"Module 8 completed with {result['data_sources_available']}/{result['total_data_sources']} data sources")
            return result
        
        return self._run_module_with_cache(stock_code, 8, _fetch_data)
    
    @staticmethod
    def _extract_api_rows(api_data: Dict) -> List[Dict]:
        if "error" in api_data or not api_data.get("result"):
            return []
        return api_data.get("result", {}).get("data") or []

    @staticmethod
    def _rank_to_score(rank) -> float:
        try:
            if rank is None:
                return 0.0
            return max(0.0, min(100.0, (1 - float(rank)) * 100))
        except (TypeError, ValueError):
            return 0.0

    def _generate_financial_evaluation_summary(
        self, financial_signals: Dict, financial_analysis: Dict
    ) -> Dict:
        """Generate financial evaluation summary from signals + analysis APIs"""
        summary = {
            "overall_financial_score": 0,
            "financial_health_score": 0,
            "profitability_score": 0,
            "growth_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "financial_metrics": {},
            "risk_factors": []
        }

        analysis_rows = self._extract_api_rows(financial_analysis)
        signal_rows = self._extract_api_rows(financial_signals)

        if analysis_rows:
            latest = analysis_rows[0]
            profit_score = self._rank_to_score(latest.get("WEIGHT_ROE_RANK"))
            growth_score = self._rank_to_score(latest.get("NETPROFIT_YOY_RATIO_RANK"))
            safety_score = self._rank_to_score(latest.get("DEBT_ASSET_RATIO_RANK"))
            operation_score = self._rank_to_score(latest.get("TOTAL_ASSETS_TR_RANK"))
            cash_score = self._rank_to_score(latest.get("SALE_CASH_RATIO_RANK"))
            dimension_scores = [s for s in [profit_score, growth_score, safety_score, operation_score, cash_score] if s > 0]
            total_score = sum(dimension_scores) / len(dimension_scores) if dimension_scores else 0.0

            summary["financial_metrics"] = {
                "total_score": round(total_score, 1),
                "profit_score": round(profit_score, 1),
                "growth_score": round(growth_score, 1),
                "safety_score": round(safety_score, 1),
                "operation_score": round(operation_score, 1),
                "cash_score": round(cash_score, 1),
                "roe": latest.get("WEIGHT_ROE"),
                "debt_ratio": latest.get("DEBT_ASSET_RATIO"),
                "gross_margin": latest.get("GROSS_RPOFIT_RATIO"),
                "net_margin": latest.get("SALE_NPR"),
                "revenue_growth": latest.get("TOTAL_OPERATE_INCOME_RATIO"),
                "profit_growth": latest.get("NETPROFIT_YOY_RATIO"),
                "report_date": latest.get("REPORT_DATE"),
                "date_type": latest.get("DATE_TYPE"),
            }

            summary["financial_health_score"] = round(safety_score, 1)
            summary["profitability_score"] = round(profit_score, 1)
            summary["growth_score"] = round(growth_score, 1)
            summary["overall_financial_score"] = round(total_score, 1)

            if total_score >= 80:
                summary["analysis"].append(f"财务综合评分{total_score:.1f}分，财务状况优秀")
                summary["recommendation"] = "财务优秀"
            elif total_score >= 70:
                summary["analysis"].append(f"财务综合评分{total_score:.1f}分，财务状况良好")
                summary["recommendation"] = "财务良好"
            elif total_score >= 60:
                summary["analysis"].append(f"财务综合评分{total_score:.1f}分，财务状况一般")
                summary["recommendation"] = "财务一般"
            elif total_score >= 40:
                summary["analysis"].append(f"财务综合评分{total_score:.1f}分，财务状况较差")
                summary["recommendation"] = "财务较差"
            else:
                summary["analysis"].append(f"财务综合评分{total_score:.1f}分，财务状况差")
                summary["recommendation"] = "财务差"

            if profit_score >= 70:
                summary["analysis"].append("盈利能力较强")
            elif profit_score < 40:
                summary["analysis"].append("盈利能力较弱")
                summary["risk_factors"].append("盈利能力不足")

            if growth_score >= 70:
                summary["analysis"].append("成长性较好")
            elif growth_score < 40:
                summary["analysis"].append("成长性较差")
                summary["risk_factors"].append("成长性不足")

            if safety_score >= 70:
                summary["analysis"].append("财务安全性较高")
            elif safety_score < 40:
                summary["analysis"].append("财务安全性较低")
                summary["risk_factors"].append("财务风险较高")

        for sig in signal_rows:
            explain = sig.get("SIGNAL_NAME_EXPLAIN")
            if explain:
                summary["analysis"].append(explain)
            if sig.get("TYPE") == "利空":
                risk_name = sig.get("SIGNAL_OTHER_NAME") or explain
                if risk_name and risk_name not in summary["risk_factors"]:
                    summary["risk_factors"].append(risk_name)

        if not analysis_rows and not signal_rows:
            if "error" in financial_analysis or "error" in financial_signals:
                summary["analysis"].append("无法获取财务评估数据")
            else:
                summary["analysis"].append("暂无财务评估数据")

        return summary
    
    def _generate_dragon_tiger_margin_summary(self, dragon_tiger_data: Dict, 
                                            margin_trading_data: Dict) -> Dict:
        """Generate dragon tiger board and margin trading summary"""
        summary = {
            "overall_board_score": 0,
            "dragon_tiger_score": 0,
            "margin_trading_score": 0,
            "recommendation": "neutral",
            "analysis": [],
            "dragon_tiger_metrics": {},
            "margin_trading_metrics": {},
            "risk_factors": []
        }
        
        # Analyze dragon tiger board data
        if "error" not in dragon_tiger_data and dragon_tiger_data.get("result") and dragon_tiger_data.get("result", {}).get("data"):
            lhb_list = dragon_tiger_data["result"]["data"]
            if lhb_list:
                latest_lhb = lhb_list[0]
                
                # Extract key metrics
                buy_amount = float(latest_lhb.get("BUY_AMOUNT", 0))
                sell_amount = float(latest_lhb.get("SELL_AMOUNT", 0))
                net_amount = buy_amount - sell_amount
                trade_date = latest_lhb.get("TRADE_DATE", "")
                
                summary["dragon_tiger_metrics"] = {
                    "buy_amount": buy_amount,
                    "sell_amount": sell_amount,
                    "net_amount": net_amount,
                    "trade_date": trade_date
                }
                
                # Score dragon tiger board activity
                if net_amount > 100000000:  # 1亿以上
                    lhb_score = 85
                    summary["analysis"].append(f"龙虎榜净买入{net_amount/100000000:.2f}亿元，资金关注度高")
                elif net_amount > 0:
                    lhb_score = 70
                    summary["analysis"].append(f"龙虎榜净买入{net_amount/100000000:.2f}亿元，资金关注度中等")
                elif net_amount > -100000000:
                    lhb_score = 50
                    summary["analysis"].append(f"龙虎榜净卖出{abs(net_amount)/100000000:.2f}亿元，资金关注度一般")
                else:
                    lhb_score = 30
                    summary["analysis"].append(f"龙虎榜净卖出{abs(net_amount)/100000000:.2f}亿元，资金关注度低")
                
                summary["dragon_tiger_score"] = lhb_score
            else:
                summary["analysis"].append("暂无龙虎榜数据")
        else:
            summary["analysis"].append("无法获取龙虎榜数据")
        
        # Analyze margin trading data
        if "error" not in margin_trading_data and margin_trading_data.get("result") and margin_trading_data.get("result", {}).get("data"):
            rzrq_list = margin_trading_data["result"]["data"]
            if rzrq_list:
                latest_rzrq = rzrq_list[0]
                
                # Extract key metrics
                margin_balance = float(latest_rzrq.get("FIN_BALANCE", 0))
                short_balance = float(latest_rzrq.get("SHORT_BALANCE", 0))
                balance_diff = margin_balance - short_balance
                free_ratio = float(latest_rzrq.get("FREE_RATIO", 0))
                trade_date = latest_rzrq.get("TRADE_DATE", "")
                
                summary["margin_trading_metrics"] = {
                    "margin_balance": margin_balance,
                    "short_balance": short_balance,
                    "balance_diff": balance_diff,
                    "free_ratio": free_ratio,
                    "trade_date": trade_date
                }
                
                # Score margin trading activity
                if balance_diff > 1000000000:  # 10亿以上
                    rzrq_score = 85
                    summary["analysis"].append(f"融资融券差额{balance_diff/1000000000:.2f}亿元，市场信心强")
                elif balance_diff > 500000000:  # 5亿以上
                    rzrq_score = 75
                    summary["analysis"].append(f"融资融券差额{balance_diff/1000000000:.2f}亿元，市场信心较好")
                elif balance_diff > 0:
                    rzrq_score = 65
                    summary["analysis"].append(f"融资融券差额{balance_diff/1000000000:.2f}亿元，市场信心一般")
                elif balance_diff > -500000000:
                    rzrq_score = 45
                    summary["analysis"].append(f"融资融券差额{balance_diff/1000000000:.2f}亿元，市场信心偏弱")
                else:
                    rzrq_score = 25
                    summary["analysis"].append(f"融资融券差额{balance_diff/1000000000:.2f}亿元，市场信心弱")
                
                summary["margin_trading_score"] = rzrq_score
                
                # Risk factors
                if balance_diff < -1000000000:
                    summary["risk_factors"].append("融资融券大幅净流出")
                if free_ratio > 10:
                    summary["risk_factors"].append("融资融券占流通市值比例较高")
            else:
                summary["analysis"].append("暂无融资融券数据")
        else:
            summary["analysis"].append("无法获取融资融券数据")
        
        # Calculate overall board score
        scores = [summary["dragon_tiger_score"], summary["margin_trading_score"]]
        valid_scores = [s for s in scores if s > 0]
        
        if valid_scores:
            summary["overall_board_score"] = sum(valid_scores) / len(valid_scores)
        else:
            summary["overall_board_score"] = 0
        
        # Generate recommendation
        if summary["overall_board_score"] >= 75:
            summary["recommendation"] = "资金关注度高"
            summary["analysis"].append("龙虎榜和融资融券显示资金关注度高")
        elif summary["overall_board_score"] >= 60:
            summary["recommendation"] = "资金关注度中等"
            summary["analysis"].append("龙虎榜和融资融券显示资金关注度中等")
        elif summary["overall_board_score"] >= 40:
            summary["recommendation"] = "资金关注度一般"
            summary["analysis"].append("龙虎榜和融资融券显示资金关注度一般")
        else:
            summary["recommendation"] = "资金关注度低"
            summary["analysis"].append("龙虎榜和融资融券显示资金关注度低")
        
        return summary
    
    def run_module(self, module_num: int) -> Dict:
        """Run a specific module by number"""
        module_functions = {
            1: self.run_module_1,
            2: self.run_module_2,
            3: self.run_module_3,
            4: self.run_module_4,
            5: self.run_module_5,
            6: self.run_module_6,
            7: self.run_module_7,
            8: self.run_module_8
        }
        
        if module_num in module_functions:
            return module_functions[module_num]()
        else:
            return {"error": f"Module {module_num} not found"}
    
    def get_available_modules(self) -> List[Dict]:
        """Get list of available modules"""
        modules = [
            {"id": 1, "name": "综合评价", "name_en": "Comprehensive Evaluation", "status": "implemented"},
            {"id": 2, "name": "主力控盘", "name_en": "Main Force Control", "status": "implemented"},
            {"id": 3, "name": "舆情监控", "name_en": "Public Opinion Monitoring", "status": "implemented"},
            {"id": 4, "name": "市场参与意愿", "name_en": "Market Participation Willingness", "status": "implemented"},
            {"id": 5, "name": "趋势研判", "name_en": "Trend Analysis", "status": "implemented"},
            {"id": 6, "name": "资金动向", "name_en": "Capital Flow", "status": "implemented"},
            {"id": 7, "name": "财务评估", "name_en": "Financial Evaluation", "status": "implemented"},
            {"id": 8, "name": "龙虎榜和融资融券", "name_en": "Dragon Tiger Board and Margin Trading", "status": "implemented"}
        ]
        return modules
    
    def clear_cache(self, stock_code: Optional[str] = None):
        """
        Clear cache for a specific stock or all stocks
        
        Args:
            stock_code: Stock code to clear, or None to clear all
        """
        if not self.cache_enabled:
            return
            
        if stock_code:
            stock_dir = self.cache_dir / stock_code
            if stock_dir.exists():
                for file in stock_dir.glob("*.json"):
                    file.unlink()
                logger.info(f"Cleared cache for {stock_code}")
        else:
            for stock_dir in self.cache_dir.iterdir():
                if stock_dir.is_dir():
                    for file in stock_dir.glob("*.json"):
                        file.unlink()
            logger.info("Cleared all cache")
    
    def get_cache_info(self, stock_code: str) -> Dict:
        """Get cache information for a stock"""
        if not self.cache_enabled:
            return {"cache_enabled": False}
            
        stock_dir = self.cache_dir / stock_code
        
        if not stock_dir.exists():
            return {"cached_modules": 0, "total_modules": 8, "modules": {}}
        
        info = {
            "cached_modules": 0,
            "total_modules": 8,
            "modules": {}
        }
        
        for i in range(1, 9):  # 8 modules
            cache_file = stock_dir / f"module_{i}.json"
            if cache_file.exists():
                file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                is_valid = datetime.now() - file_mtime <= self.cache_duration
                
                info["modules"][f"module_{i}"] = {
                    "cached": True,
                    "valid": is_valid,
                    "cached_at": file_mtime.isoformat(),
                    "expires_at": (file_mtime + self.cache_duration).isoformat()
                }
                
                if is_valid:
                    info["cached_modules"] += 1
            else:
                info["modules"][f"module_{i}"] = {
                    "cached": False,
                    "valid": False
                }
        
        return info


def main():
    """Main function to test the application"""
    app = StockCommentApp()
    
    print("=== Stock Comment App ===")
    print("股票评论应用")
    print()
    
    # Show available modules
    modules = app.get_available_modules()
    print("Available Modules:")
    for module in modules:
        status_icon = "✅" if module["status"] == "implemented" else "⏳"
        print(f"{status_icon} {module['id']}. {module['name']} ({module['name_en']})")
    
    print()
    
    # Interactive module selection
    while True:
        try:
            choice = input("\nSelect a module (1-7) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                print("Goodbye!")
                break
            
            module_num = int(choice)
            if 1 <= module_num <= 8:
                print(f"\nRunning Module {module_num}...")
                
                # Special handling for Module 1, 2, 3, 4, 5, 6, 7, and 8 (stock code input)
                if module_num in [1, 2, 3, 4, 5, 6, 7, 8]:
                    default_code = "002916" if module_num in [1, 2, 4, 5, 6, 7, 8] else "002230"
                    stock_code = input(f"Enter stock code (default: {default_code}): ").strip()
                    if not stock_code:
                        stock_code = default_code
                    if module_num == 1:
                        result = app.run_module_1(stock_code)
                    elif module_num == 2:
                        result = app.run_module_2(stock_code)
                    elif module_num == 3:
                        result = app.run_module_3(stock_code)
                    elif module_num == 4:
                        result = app.run_module_4(stock_code)
                    elif module_num == 5:
                        result = app.run_module_5(stock_code)
                    elif module_num == 6:
                        result = app.run_module_6(stock_code)
                    elif module_num == 7:
                        result = app.run_module_7(stock_code)
                    elif module_num == 8:
                        result = app.run_module_8(stock_code)
                else:
                    result = app.run_module(module_num)
                
                # print("\nResult:")
                # print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("Please enter a number between 1 and 7")
                
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
