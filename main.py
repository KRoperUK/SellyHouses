# HouseHunt Scraper
from bs4 import BeautifulSoup
from requests import get
from requests.structures import CaseInsensitiveDict
from re import findall, match

import urllib.parse, json, os, datetime

DATE_TODAY = datetime.datetime.today().strftime('%d/%m/%Y')
REGEX_DATE = r'^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$'
GEOAPIFY_API_KEY = os.getenv('GEOAPIFY_API_KEY')

def log(message, level="VERBOSE"):
    if level == "VERBOSE":
        print(f'[DEBUG] {message}')

def geocode_property(property):
    log(f"Geocoding {property['title']}")
    
    try:
        url = "https://api.geoapify.com/v1/geocode/search?"
        
        if 'address' in property:
            params = {"text": property['address'], "apiKey": GEOAPIFY_API_KEY}
        elif 'title' in property:
            if 'source' in property:
                if property['source'] == "Easy Lettings":
                    params = {"text": property['url'][46:-1].replace("-", " "), "apiKey": GEOAPIFY_API_KEY}
            else:
                params = {"text": property['title'] + " Selly Oak", "apiKey": GEOAPIFY_API_KEY}

        url += urllib.parse.urlencode(params)

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        resp = get(url, headers=headers)

        if resp.status_code == 401:
            log(f"ERROR - Geocoding status 401 for f{property}. Check API key.")
        
        if 'address' not in property:
            property['address'] = resp.json()['features'][0]['properties']['formatted']
        if resp.status_code == 200:
            # pass
            # property['location'] = resp.json()['features'][0]['properties']['address']
            property['lat'] = resp.json()['features'][0]['properties']['lat']
            property['lon'] = resp.json()['features'][0]['properties']['lon']
        else:
            log(f"ERROR - Geocoding status not 200 for f{property}, status code {resp.status_code}")
    except:
        log(f"ERROR - Could not find more information about f{property}")
    return property

class house_hunt():

    def __init__(self) -> None:
        self.properties = []

        self.BASE_LINK = "https://www.househuntltd.co.uk/properties/lettings"

        soup = BeautifulSoup(get(self.BASE_LINK).text, features="lxml")

        page_info = findall(r'[0-9]', soup.find('span', class_='page-number').text)
        self.pages = page_info[1]

    def find_first(self):
        self.get_page_info(self.BASE_LINK)

        new_properties = []
        for property in self.properties:
            log(f"Getting more data about... {property['title']}")
            property = self.get_property_info(property['url'], property)

            new_properties.append(property)
        self.properties = new_properties

        
    def find_all(self):
        urls = []
        for i in range(1, int(self.pages)):
            urls.append(self.BASE_LINK + f'?start={i * 60}')

        self.get_page_info(self.BASE_LINK)
        for url in urls:
            self.get_page_info(url)

        new_properties = []
        for property in self.properties:
            log(f"Getting more data about... {property['title']}")
            property = self.get_property_info(property['url'], property)

            new_properties.append(property)
        self.properties = new_properties


    def get_page_info(self, url):
        properties = []

        soup = BeautifulSoup(get(url).text, features="lxml")

        table = soup.find_all('div', class_='properties')
        page_properties = table[0].find_all('div', class_='grid')
        for property in page_properties:
            x = {}
            x_span = property.find('span', class_='title')
            x['title'] = x_span.find('a').text.split(',')[0]

            log(f"Getting basic data about... {x['title']}")

            x['source'] = "House Hunt"            
            x['address'] = x_span.find('a').text
            x['url'] = "https://www.househuntltd.co.uk" + x_span.find('a')['href']
            x['price'] = property.find('span', class_='price').text
            
            x_property_size = property.find('span', class_='property-size')
            x_property_size = findall(r'[0-9]', x_property_size.text)


            # TODO FIX THIS, 115 Tiv.
            if len(x_property_size) == 2:
                x['beds'] = x_property_size[0]
                x['baths'] = x_property_size[1]
            elif len(x_property_size) == 3:
                x['beds'] = x_property_size[0:1]
                x['baths'] = x_property_size[2]
            elif len(x_property_size) == 4:
                x['beds'] = x_property_size[0:1]
                x['baths'] = x_property_size[2:3]
            # x['beds'] = x_property_size.text.split(' ')[0]

            properties.append(x)
        self.properties = self.properties + properties

    def get_property_info(self, url, property):
        soup = BeautifulSoup(get(url).text, features="lxml")

        content = soup.find_all('div', id='content')[0]
        available_date = content.find_all('div', class_="grid alert alert-error")
        if len(available_date) < 1:
            available_date = content.find_all('div', class_="grid alert alert-success")
        if len(available_date) < 1:
            property['available_date'] = "Unknown"
        else:
            property['available_date'] = available_date[0].text.split(':')[1].strip()

        try:
            slides = soup.find('div', class_='flexslider').find_all('img')

            if len(slides) > 0:
                property['images'] = []

                for img in slides:
                    if img['src']:
                        if 'media' in img['src']:
                            property['images'].append("https://www.househuntltd.co.uk" + img['src'])
        except:
            log(f"ERROR - Could not find images for {property['title']}")
        
        property = geocode_property(property)

        return property
    def save_to_json(self):
        log(f"House Hunt - Saving to JSON")
        with open('house_hunt.json', 'w') as f:
            json.dump(self.properties, f, sort_keys=True, indent=4)
    
class easy_lettings():

    def __init__(self) -> None:
        self.BASE_LINK = "https://easylettingsbirmingham.co.uk/property-list/?department=residential-lettings&marketing_flag=67&marketing_flag_id=67"
        self.properties = []

        soup = BeautifulSoup(get(self.BASE_LINK).text, features="lxml")

        page_buttons = soup.find('ul', class_='page-numbers').find_all('li')

        self.pages = page_buttons[-2].text
    
    def find_first(self):
        self.get_page_info(self.BASE_LINK)

        new_properties = []
        for property in self.properties:
            new_properties.append(self.get_property_info(property['url'], property))
        self.properties = new_properties

    def find_all(self):
        for i in range(1, int(self.pages) + 1):
        # for i in range(1, 2):
            self.get_page_info(f"https://easylettingsbirmingham.co.uk/property-list/page/{i}/?department=residential-lettings&marketing_flag=67&marketing_flag_id=67")
        
        new_properties = []
        for property in self.properties:
            new_properties.append(self.get_property_info(property['url'], property))
        self.properties = new_properties

    def get_page_info(self, url):
        log(f"Getting page info from... {url}")

        soup = BeautifulSoup(get(url).text, features="lxml")
        property_list = soup.find('ul', class_='property_ul')
        properties_raw = property_list.find_all('li')

        for property_raw in properties_raw:
            property = {}

            property['source'] = "Easy Lettings"
            property['url'] = property_raw.find('div', class_="link-holder").find('a')['href']
            property['title'] = property_raw.find('div', class_="address_holder").find('h5').text
            log(f"Getting basic data about... {property['title']}")
            # property['title'] = property_raw.find('h3').text
            # property['address'] = property_raw.find('p', class_='address').text
            raw_price = property_raw.find('div', class_='price').text.strip().split('£')
            try:
                property['price'] = f"£{raw_price[1]} {raw_price[0]}"
            except:
                property['price'] = "".join(raw_price)
            
            icon_data = property_raw.find_all('div', {'class': 'icons-holder'})

            if property_raw.find('div', class_='sold_text'):
                if property_raw.find('div', class_='sold_text').text == "Let":
                    property['status'] = "Let"
            else:
                property['status'] = "Unknown"

            for icon_datum in icon_data:
                if icon_datum.find('div', class_='property_icon_title').text == "Bedrooms":
                    property['beds'] = icon_datum.find('div', class_="property_icons").text.strip()
                elif icon_datum.find('div', class_='property_icon_title').text == "Bathrooms":
                    property['baths'] = icon_datum.find('div', class_="property_icons").text.strip()
            self.properties.append(property)

    def get_property_info(self, url, property):
        property = geocode_property(property)

        soup = BeautifulSoup(get(url).text, features="lxml")

        div_content_text = soup.find('div', class_='content_holder').text

        div_content_text_line_by_line = div_content_text.split('\n')

        property['available_date'] = "Unknown"

        for line in div_content_text_line_by_line:
            line = line.lower()

            if "available now" in line:
                property['available_date'] = DATE_TODAY

            elif "available from: " in line:
                raw_date = line.split('available from:')[1].strip()
                # log(f"Found available date... {raw_date} about {property['title']}")

                if match(REGEX_DATE, raw_date):
                    property['available_date'] = raw_date
                elif ' ' in raw_date:
                    property['available_date'] = raw_date.split(' ')[0]

            elif "available: " in line:
                raw_date = line.split('available:')[1].strip()
                # log(f"Found available date... {raw_date} about {property['title']}")

                if match(REGEX_DATE, raw_date):
                    property['available_date'] = raw_date
                elif ' ' in raw_date:
                    property['available_date'] = raw_date.split(' ')[0]
            
            elif "available " in line:
                raw_date = line.split('available ')[1].strip()
                # log(f"Found available date... {raw_date} about {property['title']}")

                if match(REGEX_DATE, raw_date):
                    property['available_date'] = raw_date
                elif ' ' in raw_date:
                    raw_date = raw_date.split(' ')[0]
                    if match(REGEX_DATE, raw_date):
                        property['available_date'] = raw_date
        if property['available_date'] == "Unknown":
            log(f"ERROR - Could not find date for {property['title']}")

        images = soup.find_all('img', class_='owl-img')

        property['images'] = []

        if images:
            for img in images:
                try:
                    property['images'].append(img.parent['style'].split('url(')[1][:-1].split(')')[0])
                except:
                    log(f"ERROR - Could not find image link {img['alt']} for {property['title']}")
        else:
            log(f"ERROR - Could not find images for {property['title']}")
            

        return property
    def save_to_json(self):
        log(f"Easy Lettings - Saving to JSON")
        with open('easy_lettings.json', 'w') as f:
            # print(y.properties)
            json.dump(self.properties, f, sort_keys=True, indent=4)

x = house_hunt()
x.find_all()
# x.find_first()
x.save_to_json()

y = easy_lettings()
# y.find_first()
y.find_all()
y.save_to_json()

with open('combined.json', 'w') as f:
    json.dump(x.properties + y.properties, f, sort_keys=True, indent=4)