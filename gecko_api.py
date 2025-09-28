import requests


def fetch_top_coins(limit=100):
    """Fetch top coins by market cap from CoinGecko with debug info"""
    print(f"Requesting top {limit} coins from CoinGecko...")
    
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        'vs_currency': 'usd',
        'order': 'market_cap_desc',
        'per_page': limit,
        'page': 1,
        'sparkline': False
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"API Response status: {response.status_code}")
        response.raise_for_status()
        data = response.json()
        
        print(f"API returned {len(data)} coins")
        
        coin_data = {}
        for coin in data:
            # Skip coins with null/zero prices
            if coin['current_price'] is None or coin['current_price'] <= 0:
                print(f"Skipping {coin['id']} - invalid price: {coin['current_price']}")
                continue
                
            coin_data[coin['id']] = {
                'current_price': coin['current_price'],
                'symbol': coin['symbol'].upper(),
                'name': coin['name']
            }
        
        print(f"Processed {len(coin_data)} valid coins")
        
        # Show first few coins for verification
        sample_coins = list(coin_data.items())[:5]
        print("Sample coins processed:")
        for coin_id, coin_info in sample_coins:
            print(f"  {coin_info['symbol']}: {coin_info['name']} = ${coin_info['current_price']:,.2f}")
        
        return coin_data
        
    except requests.RequestException as e:
        print(f"API Request Error: {e}")
        return {}
    except Exception as e:
        print(f"Processing Error: {e}")
        return {}

def fetch_current_prices(coin_ids):
    """Fetch specific coins - kept for compatibility"""
    if not coin_ids:
        return {}
    
    coins_string = ','.join(coin_ids)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        'vs_currency': 'usd',
        'ids': coins_string,
        'order': 'market_cap_desc',
        'per_page': 250,
        'page': 1,
        'sparkline': False
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        coin_data = {}
        for coin in data:
            coin_data[coin['id']] = {
                'current_price': coin['current_price'],
                'symbol': coin['symbol'].upper(),
                'name': coin['name']
            }
        
        return coin_data
        
    except Exception as e:
        print(f"Error fetching from CoinGecko: {e}")
        return {}