import requests
from typing import Optional, Dict
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import socket
import struct

class IPService:
    def __init__(self):
        self.api_url = "https://ipapi.co/json/"
        
    def get_real_ip(self, request) -> str:
        """
        Real IP manzilini olish
        Args:
            request: FastAPI request object
        Returns:
            str: Real IP manzili
        """
        # Agar local hostdan ishlayapsak, user_id dan IP manzilni olish
        if request.client.host == '127.0.0.1':
            # User ID dan IP manzilni olish
            return '127.0.0.1'  # Local host IP
            
        # X-Real-IP va X-Forwarded-For headerlarini tekshirish
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
            
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Birinchi IP manzilni olish
            return forwarded_for.split(',')[0].strip()
            
        # Agar headerlar mavjud bo'lmasa, request.client.host dan olish
        return request.client.host
        
    async def get_country_code(self, ip_address: str) -> Optional[str]:
        """
        IP manzilidan davlat kodini olish
        Args:
            ip_address: IP manzil
        Returns:
            Optional[str]: Davlat kodi (masalan: 'UZ' yoki None)
        """
        try:
            # Offline rejimda ishlashi uchun
            if ip_address == '127.0.0.1':
                return 'UZ'  # Lokal IP uchun o'zbekiston davlat kodini qaytarish
                
            # Agar IP xizmati ishlayotgan bo'lsa, onlayn so'rov yuborish
            response = requests.get(f"https://ipapi.co/{ip_address}/json/")
            if response.status_code == 200:
                data = response.json()
                return data.get('country_code')
            return 'UZ'  # Xatolik yuz berganda o'zbekiston davlat kodini qaytarish
        except Exception as e:
            print(f"IP geolocation xatosi: {str(e)}")
            return 'UZ'  # Xatolik yuz berganda o'zbekiston davlat kodini qaytarish

    async def get_country_from_ip(self, ip_address: str) -> Optional[Dict]:
        """
        IP manzilidan barcha davlat ma'lumotlarini olish
        Args:
            ip_address: IP manzil
        Returns:
            Optional[Dict]: Davlat ma'lumotlari (country, region, city, latitude, longitude, timezone)
        """
        try:
            response = requests.get(f"https://ipapi.co/{ip_address}/json/")
            if response.status_code == 200:
                data = response.json()
                return {
                    'country': data.get('country_name'),
                    'country_code': data.get('country_code'),
                    'region': data.get('region'),
                    'city': data.get('city'),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('timezone')
                }
            return None
        except Exception as e:
            print(f"IP geolocation xatosi: {str(e)}")
            return None

    async def get_country_name(self, ip_address: str) -> Optional[str]:
        """
        IP manzilidan davlat nomini olish
        Args:
            ip_address: IP manzil
        Returns:
            Optional[str]: Davlat nomi (masalan: 'Uzbekistan' yoki None)
        """
        try:
            response = requests.get(f"https://ipapi.co/{ip_address}/json/")
            if response.status_code == 200:
                data = response.json()
                return data.get('country_name')
            return None
        except Exception as e:
            print(f"IP geolocation xatosi: {str(e)}")
            return None
