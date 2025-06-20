from geoip2.database import Reader
import os
from typing import Optional, Dict

class GeoLocationService:
    def __init__(self):
        # Download GeoLite2-Country.mmdb if not exists
        geoip_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'GeoLite2-Country.mmdb')
        if not os.path.exists(geoip_db_path):
            os.makedirs(os.path.dirname(geoip_db_path), exist_ok=True)
            # Download database
            import requests
            import zipfile
            from io import BytesIO
            
            url = "https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.mmdb.gz"
            response = requests.get(url)
            with open(geoip_db_path, 'wb') as f:
                f.write(response.content)
        
        self.reader = Reader(geoip_db_path)
    
    def get_country_from_ip(self, ip: str) -> Optional[Dict]:
        """
        Get country information from IP address
        
        Args:
            ip: IP address to look up
            
        Returns:
            Dictionary with country code and name, or None if not found
        """
        try:
            response = self.reader.country(ip)
            return {
                'country_code': response.country.iso_code,
                'country_name': response.country.name
            }
        except Exception:
            return None
