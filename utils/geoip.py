import requests
from typing import Dict, Optional, Any
import logging
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


class GeoIPService:
    """Service for handling IP geolocation lookups."""
    
    @staticmethod
    async def get_location_from_ip(ip: str) -> Dict[str, Any]:
        """
        Get location information from an IP address.
        
        Args:
            ip: IP address to look up
            
        Returns:
            Dictionary containing location information
        """
        try:
            # First try ip-api.com (free tier available)
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,lat,lon,timezone,query")
            data = response.json()
            
            if data.get('status') == 'success':
                return {
                    'ip': data.get('query', ip),
                    'country': data.get('country'),
                    'region': data.get('regionName'),
                    'city': data.get('city'),
                    'latitude': data.get('lat'),
                    'longitude': data.get('lon'),
                    'timezone': data.get('timezone')
                }
            
            # Fallback to ipinfo.io if first service fails
            response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=5)
            data = response.json()
            
            if 'loc' in data:
                lat, lon = data['loc'].split(',')
                return {
                    'ip': data.get('ip', ip),
                    'country': data.get('country'),
                    'region': data.get('region'),
                    'city': data.get('city'),
                    'latitude': float(lat),
                    'longitude': float(lon),
                    'timezone': data.get('timezone')
                }
                
        except Exception as e:
            logger.error(f"Error getting location from IP {ip}: {str(e)}")
            
        # Return minimal data if all lookups fail
        return {
            'ip': ip,
            'country': None,
            'region': None,
            'city': None,
            'latitude': None,
            'longitude': None,
            'timezone': None
        }
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """
        Get the client's IP address from the request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client's IP address as string
        """
        if 'x-forwarded-for' in request.headers:
            # If behind a proxy, the first IP is the client's
            return request.headers['x-forwarded-for'].split(',')[0].strip()
        return request.client.host if request.client else '127.0.0.1'
