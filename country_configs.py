"""
VFS Country-Specific Configurations
Each country may have different URL patterns and selectors
"""

COUNTRY_CONFIGS = {
    'deu': {
        'name': 'Germany',
        'base_url': 'https://visa.vfsglobal.com/tur/en/deu',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/deu/book-an-appointment',
        'selectors': {
            # Main appointment availability indicator
            'no_appointment': [
                'text=No appointment slots are currently available',
                'text=Şu anda randevu slotu bulunmamaktadır',
                '.no-appointment-message',
                '.alert-warning:has-text("available")',
            ],
            # Available appointment slots
            'appointment_slots': [
                '.appointment-slot.available',
                'button.appointment-date:not([disabled])',
                '[data-available="true"]',
                '.calendar-day.available',
            ],
            # Date elements
            'dates': [
                '.appointment-date',
                '.calendar-date',
                '[data-date]',
            ],
            # Loading indicators
            'loading': [
                '.loading',
                '.spinner',
                'text=Loading',
            ],
        },
        'wait_for':
        '.appointment-calendar, .appointment-slots, .no-appointment-message',
        'timeout': 30000,
    },
    'bel': {
        'name': 'Belgium',
        'base_url': 'https://visa.vfsglobal.com/tur/en/bel',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/bel/book-an-appointment',
        'selectors': {
            'no_appointment': [
                'text=No appointment slots are currently available',
                'text=Şu anda randevu slotu bulunmamaktadır',
                '.no-appointment-message',
            ],
            'appointment_slots': [
                '.appointment-slot.available',
                'button.appointment-date:not([disabled])',
            ],
            'dates': [
                '.appointment-date',
            ],
            'loading': [
                '.loading',
            ],
        },
        'wait_for': '.appointment-calendar, .appointment-slots',
        'timeout': 30000,
    },
    'esp': {
        'name': 'Spain',
        'base_url': 'https://visa.vfsglobal.com/tur/en/esp',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/esp/book-an-appointment',
        'selectors': {
            'no_appointment': [
                'text=No appointment slots are currently available',
                'text=Şu anda randevu slotu bulunmamaktadır',
                '.no-appointment-message',
            ],
            'appointment_slots': [
                '.appointment-slot.available',
                'button.appointment-date:not([disabled])',
            ],
            'dates': [
                '.appointment-date',
            ],
            'loading': [
                '.loading',
            ],
        },
        'wait_for': '.appointment-calendar, .appointment-slots',
        'timeout': 30000,
    },
    'fra': {
        'name': 'France',
        'base_url': 'https://visa.vfsglobal.com/tur/en/fra',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/fra/book-an-appointment',
        'selectors': {
            'no_appointment': [
                'text=No appointment slots are currently available',
                '.no-appointment-message',
            ],
            'appointment_slots': [
                '.appointment-slot.available',
            ],
            'dates': [
                '.appointment-date',
            ],
            'loading': [
                '.loading',
            ],
        },
        'wait_for': '.appointment-calendar',
        'timeout': 30000,
    },
    'ita': {
        'name': 'Italy',
        'base_url': 'https://visa.vfsglobal.com/tur/en/ita',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/ita/book-an-appointment',
        'selectors': {
            'no_appointment': [
                'text=No appointment slots are currently available',
                '.no-appointment-message',
            ],
            'appointment_slots': [
                '.appointment-slot.available',
            ],
            'dates': [
                '.appointment-date',
            ],
            'loading': [
                '.loading',
            ],
        },
        'wait_for': '.appointment-calendar',
        'timeout': 30000,
    },
    'nld': {
        'name': 'Netherlands',
        'base_url': 'https://visa.vfsglobal.com/tur/en/nld',
        'appointment_url':
        'https://visa.vfsglobal.com/tur/en/nld/book-an-appointment',
        'selectors': {
            'no_appointment': [
                'text=No appointment slots are currently available',
                '.no-appointment-message',
            ],
            'appointment_slots': [
                '.appointment-slot.available',
            ],
            'dates': [
                '.appointment-date',
            ],
            'loading': [
                '.loading',
            ],
        },
        'wait_for': '.appointment-calendar',
        'timeout': 30000,
    },
}


def get_country_config(country_code: str) -> dict:
    """
    Get configuration for a specific country

    Args:
        country_code: Country code (e.g., 'deu', 'bel')

    Returns:
        Country configuration dict, or default config if not found
    """
    return COUNTRY_CONFIGS.get(
        country_code.lower(), {
            'name': country_code.upper(),
            'base_url':
            f'https://visa.vfsglobal.com/tur/en/{country_code.lower()}',
            'appointment_url':
            f'https://visa.vfsglobal.com/tur/en/{country_code.lower()}/book-an-appointment',
            'selectors': {
                'no_appointment': [
                    'text=No appointment slots are currently available',
                    'text=Şu anda randevu slotu bulunmamaktadır',
                ],
                'appointment_slots': [
                    '.appointment-slot.available',
                ],
                'dates': [
                    '.appointment-date',
                ],
                'loading': [
                    '.loading',
                ],
            },
            'wait_for': '.appointment-calendar',
            'timeout': 30000,
        })


def list_supported_countries():
    """List all supported countries"""
    return [{
        'code': code,
        'name': config['name']
    } for code, config in COUNTRY_CONFIGS.items()]
