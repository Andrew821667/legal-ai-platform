# -*- coding: utf-8 -*-
"""
FNS API Integration - Federal Tax Service (ФНС) API client

Интеграция с API ФНС для проверки контрагентов:
- ЕГРЮЛ (Единый государственный реестр юридических лиц)
- ЕГРИП (Единый государственный реестр индивидуальных предпринимателей)

API Methods:
1. Official FNS EGRUL API (free, limited)
2. Dadata.ru API (commercial, reliable)
3. Public EGRUL data
"""
import requests
import json
import time
from typing import Dict, Any, Optional
from loguru import logger
from datetime import datetime


class FNSAPIClient:
    """
    Client for FNS (Federal Tax Service) data

    Supports:
    - Company lookup by INN/OGRN
    - Basic company information
    - Registration status
    - Legal address

    Note: Official FNS API has rate limits and may require captcha
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        use_dadata: bool = False
    ):
        """
        Initialize FNS API client

        Args:
            api_key: Optional API key for premium services (Dadata, etc.)
            timeout: Request timeout in seconds
            use_dadata: Use Dadata.ru API (requires api_key)
        """
        self.api_key = api_key
        self.timeout = timeout
        self.use_dadata = use_dadata and api_key is not None

        # API endpoints
        self.egrul_url = "https://egrul.nalog.ru"
        self.dadata_url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"

        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        if self.use_dadata:
            self.headers['Authorization'] = f'Token {api_key}'
            self.headers['Content-Type'] = 'application/json'

    def get_company_info(self, inn: str) -> Dict[str, Any]:
        """
        Get company information by INN

        Args:
            inn: INN (ИНН) - 10 or 12 digits

        Returns:
            Company information dict

        Raises:
            ValueError: If INN invalid
            RuntimeError: If API request fails
        """
        # Validate INN
        if not inn or not inn.isdigit() or len(inn) not in [10, 12]:
            raise ValueError(f"Invalid INN: {inn}. Must be 10 or 12 digits.")

        logger.info(f"Fetching FNS data for INN: {inn}")

        # Try Dadata first if available (more reliable)
        if self.use_dadata:
            try:
                return self._get_from_dadata(inn)
            except Exception as e:
                logger.warning(f"Dadata API failed: {e}, falling back to EGRUL")

        # Fallback to official EGRUL API
        try:
            return self._get_from_egrul(inn)
        except Exception as e:
            logger.error(f"EGRUL API failed: {e}")

            # Return minimal stub data on complete failure
            return self._get_stub_data(inn, error=str(e))

    def _get_from_dadata(self, inn: str) -> Dict[str, Any]:
        """
        Get company info from Dadata.ru API

        Dadata provides clean, structured FNS data with good API
        Requires: API key from https://dadata.ru/

        Args:
            inn: INN

        Returns:
            Structured company data
        """
        logger.info(f"Querying Dadata API for INN: {inn}")

        try:
            payload = {"query": inn}

            response = requests.post(
                self.dadata_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )

            response.raise_for_status()
            data = response.json()

            if not data.get('suggestions'):
                logger.warning(f"No data found in Dadata for INN: {inn}")
                return {
                    'found': False,
                    'inn': inn,
                    'data_source': 'Dadata API',
                    'error': 'Not found'
                }

            # Extract first suggestion
            company = data['suggestions'][0]['data']

            result = {
                'found': True,
                'inn': inn,
                'name': {
                    'full': company.get('name', {}).get('full_with_opf'),
                    'short': company.get('name', {}).get('short_with_opf'),
                },
                'ogrn': company.get('ogrn'),
                'kpp': company.get('kpp'),
                'registration_date': company.get('state', {}).get('registration_date'),
                'active': company.get('state', {}).get('status') == 'ACTIVE',
                'status': company.get('state', {}).get('status'),
                'legal_address': company.get('address', {}).get('unrestricted_value'),
                'ceo': company.get('management', {}).get('name'),
                'authorized_capital': company.get('capital', {}).get('value'),
                'opf': company.get('opf', {}).get('short'),  # Организационно-правовая форма
                'okved': company.get('okved'),  # Основной вид деятельности
                'employee_count': company.get('employee_count'),
                'data_source': 'Dadata API'
            }

            logger.info(f"✓ Dadata: Found company {result['name']['short']}")
            return result

        except requests.RequestException as e:
            logger.error(f"Dadata API request failed: {e}")
            raise RuntimeError(f"Dadata API error: {e}")

    def _get_from_egrul(self, inn: str) -> Dict[str, Any]:
        """
        Get company info from official FNS EGRUL

        Note: Official EGRUL API may require captcha and has rate limits
        This implementation uses public search endpoint

        Args:
            inn: INN

        Returns:
            Structured company data
        """
        logger.info(f"Querying EGRUL for INN: {inn}")

        try:
            # Step 1: Submit search request
            search_url = f"{self.egrul_url}/search-result/"

            # Prepare search payload
            payload = {
                'vyp3CaptchaToken': '',  # Captcha handling needed for production
                'page': '',
                'query': inn,
                'region': '',
                'PreventChromeAutocomplete': ''
            }

            # Submit search
            response = requests.post(
                search_url,
                data=payload,
                headers=self.headers,
                timeout=self.timeout
            )

            response.raise_for_status()

            # Parse response - EGRUL returns task ID
            result_data = response.json()
            task_id = result_data.get('t')

            if not task_id:
                logger.warning(f"No task ID received from EGRUL for INN: {inn}")
                return self._get_stub_data(inn, error="EGRUL returned no task ID")

            logger.info(f"EGRUL task ID: {task_id}, waiting for results...")

            # Step 2: Poll for results (EGRUL processes async)
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(1)  # Wait 1 second between attempts

                result_url = f"{self.egrul_url}/search-result/{task_id}"
                result_response = requests.get(
                    result_url,
                    headers=self.headers,
                    timeout=self.timeout
                )

                if result_response.status_code == 200:
                    company_data = result_response.json()

                    if company_data and 'rows' in company_data:
                        # Extract company info from first result
                        rows = company_data['rows']
                        if rows:
                            company = rows[0]
                            return self._parse_egrul_response(company, inn)

            logger.warning(f"EGRUL timeout after {max_attempts} attempts for INN: {inn}")
            return self._get_stub_data(inn, error="EGRUL timeout")

        except requests.RequestException as e:
            logger.error(f"EGRUL API request failed: {e}")
            return self._get_stub_data(inn, error=str(e))

        except Exception as e:
            logger.error(f"EGRUL parsing failed: {e}")
            return self._get_stub_data(inn, error=str(e))

    def _parse_egrul_response(self, company: Dict[str, Any], inn: str) -> Dict[str, Any]:
        """Parse EGRUL API response to structured format"""
        return {
            'found': True,
            'inn': inn,
            'name': {
                'full': company.get('n'),
                'short': company.get('c'),
            },
            'ogrn': company.get('o'),
            'kpp': company.get('p'),
            'registration_date': company.get('r'),
            'active': company.get('s') == 1,  # 1 = active
            'status': 'ACTIVE' if company.get('s') == 1 else 'INACTIVE',
            'legal_address': company.get('a'),
            'ceo': company.get('g'),
            'data_source': 'FNS EGRUL API'
        }

    def _get_stub_data(self, inn: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Return stub data when API fails"""
        logger.warning(f"Returning stub data for INN: {inn} (error: {error})")

        return {
            'found': False,
            'inn': inn,
            'name': {'full': f'Организация {inn}', 'short': f'ООО {inn}'},
            'ogrn': None,
            'registration_date': None,
            'active': False,
            'status': 'UNKNOWN',
            'legal_address': None,
            'ceo': None,
            'data_source': 'Stub (API unavailable)',
            'error': error or 'API unavailable'
        }

    def check_inn_format(self, inn: str) -> Dict[str, Any]:
        """
        Validate INN format and checksum

        INN format:
        - Legal entities: 10 digits
        - Individual entrepreneurs: 12 digits

        Returns:
            Validation result
        """
        result = {
            'valid': False,
            'inn': inn,
            'type': None,
            'errors': []
        }

        if not inn or not isinstance(inn, str):
            result['errors'].append('INN is empty or not a string')
            return result

        if not inn.isdigit():
            result['errors'].append('INN must contain only digits')
            return result

        length = len(inn)
        if length == 10:
            result['type'] = 'legal_entity'
            result['valid'] = self._validate_inn_10(inn)
        elif length == 12:
            result['type'] = 'individual'
            result['valid'] = self._validate_inn_12(inn)
        else:
            result['errors'].append(f'INN must be 10 or 12 digits, got {length}')
            return result

        if not result['valid']:
            result['errors'].append('INN checksum validation failed')

        return result

    def _validate_inn_10(self, inn: str) -> bool:
        """Validate 10-digit INN checksum"""
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(inn[i]) * coefficients[i] for i in range(9)) % 11 % 10
        return checksum == int(inn[9])

    def _validate_inn_12(self, inn: str) -> bool:
        """Validate 12-digit INN checksum"""
        coef1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        coef2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

        checksum1 = sum(int(inn[i]) * coef1[i] for i in range(10)) % 11 % 10
        checksum2 = sum(int(inn[i]) * coef2[i] for i in range(11)) % 11 % 10

        return checksum1 == int(inn[10]) and checksum2 == int(inn[11])


__all__ = ['FNSAPIClient']
