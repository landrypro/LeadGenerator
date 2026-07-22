export const initialForm = {
  query: 'plombier',
  center_latitude: 46.8139,
  center_longitude: -71.2080,
  radius_km: 15,
  target: 200,
  max_tiles: 8,
  max_pages: 3,
  contact_fields: false,
  include_service_area_businesses: true,
  language_code: 'fr',
  region_code: 'CA',
}

export const initialRequester = {
  first_name: '',
  company_name: '',
  business_address: '',
}

export const numberFormatter = new Intl.NumberFormat('fr-CA')
