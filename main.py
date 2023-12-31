# HouseHunt Scraper
from bs4 import BeautifulSoup
from requests import get
from requests.structures import CaseInsensitiveDict
from re import findall, match

import urllib.parse, json, os, datetime, threading

DATE_TODAY = datetime.datetime.today().strftime('%d/%m/%Y')
REGEX_DATE = r'^(?:(?:31(\/|-|\.)(?:0?[13578]|1[02]))\1|(?:(?:29|30)(\/|-|\.)(?:0?[13-9]|1[0-2])\2))(?:(?:1[6-9]|[2-9]\d)?\d{2})$|^(?:29(\/|-|\.)0?2\3(?:(?:(?:1[6-9]|[2-9]\d)?(?:0[48]|[2468][048]|[13579][26])|(?:(?:16|[2468][048]|[3579][26])00))))$|^(?:0?[1-9]|1\d|2[0-8])(\/|-|\.)(?:(?:0?[1-9])|(?:1[0-2]))\4(?:(?:1[6-9]|[2-9]\d)?\d{2})$'
GEOAPIFY_API_KEY = os.getenv('GEOAPIFY_API_KEY')

COLOURS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "WARNING": "\033[93m",
    "FAIL": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m"
}

def log(message, level="VERBOSE"):
    if level == "VERBOSE":
        print(f'[DEBUG] {message}')

def geocode_property(property):
    log(f"Geocoding {property['title']}")
    
    try:
        url = "https://api.geoapify.com/v1/geocode/search?"
        
        if 'address' in property:
            params = {"text": property['address'] + " United Kingdom", "apiKey": GEOAPIFY_API_KEY}
        elif 'title' in property:
            log(f"Geocoding {property['title']} no address")
            if 'source' in property:
                if property['source'] == "Easy Lettings":
                    params = {"text": property['title'] + " Birmingham, United Kingdom", "apiKey": GEOAPIFY_API_KEY}
                else:
                    params = {"text": property['title'] + " Birmingham, United Kingdom", "apiKey": GEOAPIFY_API_KEY}
            log(f"Geocoding {property['title']} with params {params}")

        url += urllib.parse.urlencode(params)
        if 'title' in property:
            log(f"Geocoding {property['title']} with url {url}")

        headers = CaseInsensitiveDict()
        headers["Accept"] = "application/json"

        resp = get(url, headers=headers)

        if resp.status_code == 401:
            log(f"ERROR - Geocoding status 401 for {property}. Check API key.")
        
        if 'address' not in property:
            property['address'] = resp.json()['features'][0]['properties']['formatted']
        if resp.status_code == 200:
            # pass
            # property['location'] = resp.json()['features'][0]['properties']['address']
            property['lat'] = resp.json()['features'][0]['properties']['lat']
            property['lon'] = resp.json()['features'][0]['properties']['lon']
        else:
            if 'title' in property:
                log(f"ERROR - Geocoding status not 200 for {property['title']}, status code {resp.status_code}")
            log(f"ERROR - Geocoding status not 200. Geocodify response: {resp.json()}")
    except:
        log(f"ERROR - Could not find more information about {property}")
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
            log(f"[HOUSE HUNT] Getting more data about... {property['title']}")
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
        for index, property in enumerate(self.properties):
            property = self.get_property_info(property['url'], property, index, len(self.properties))

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

            log(f"[HOUSE HUNT] Getting basic data about... {x['title']}")

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

    def get_property_info(self, url, property, index=0, total=0):
        log(f"[HOUSE HUNT] [{index}/{total}] Getting more data about... {property['title']}")
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
        
        # property = geocode_property(property)

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
        
        counter = 0
        new_properties = []
        for property in self.properties:
            counter += 1
            log(f"[EASY LETTINGS] [{counter} / {len(self.properties)}] Getting more data about... {property['title']}")
            new_properties.append(self.get_property_info(property['url'], property))
        self.properties = new_properties

    def get_page_info(self, url):
        log(f"[EASY LETTINGS] Getting page info from... {url}")

        soup = BeautifulSoup(get(url).text, features="lxml")
        property_list = soup.find('ul', class_='property_ul')
        properties_raw = property_list.find_all('li')

        for property_raw in properties_raw:
            property = {}

            property['source'] = "Easy Lettings"
            property['url'] = property_raw.find('div', class_="link-holder").find('a')['href']
            property['title'] = property_raw.find('div', class_="address_holder").find('h5').text
            log(f"[EASY LETTINGS] Getting basic data about... {property['title']}")
            # property['title'] = property_raw.find('h3').text
            # property['address'] = property_raw.find('p', class_='address').textz
            raw_price = property_raw.find('div', class_='price').text.strip().split('£')
            try:
                property['price'] = f"£{raw_price[1]} {raw_price[0]}"
            except:
                property['price'] = "".join(raw_price)

            # session = HTMLSession()
            # r = session.get(property['url'])
            # r.html.render()

            # for script in r.html.find('script'):
            #     try:
            #         raw_lat_long = script.text.split('L.marker([')[1].split('])')[0].split(',')
            #         property['lat'] = raw_lat_long[0].strip()
            #         property['lon'] = raw_lat_long[1].strip()
            #     except:
            #         try:
            #             raw_lat_long =  script.text.split('setView([')[1].split('],')[0].split(',')
            #             property['lat'] = raw_lat_long[0].strip()
            #             property['lon'] = raw_lat_long[1].strip()
            #         except:
            #             pass
            
            if 'lat' not in property:
                log(f"{COLOURS['FAIL']}ERROR{COLOURS['ENDC']} - Could not find lat/long for {property['title']}")

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
        soup = BeautifulSoup(get(url).text, features="lxml")

        for script in soup.find_all('script'):
            try:
                raw_lat_long = script.text.split('L.marker([')[1].split('])')[0].split(',')
                property['lat'] = raw_lat_long[0].strip()
                property['lon'] = raw_lat_long[1].strip()
                # log(f"{property['lat']}, {property['lon']}")
            except:
                # log(f"ERROR - Could not find lat/long for {property['title']} via L.marker")
                try:
                    raw_lat_long =  script.text.split('setView([')[1].split('],')[0].split(',')
                    property['lat'] = raw_lat_long[0].strip()
                    property['lon'] = raw_lat_long[1].strip()
                    # log(f"{property['lat']}, {property['lon']}")
                except:
                    # log(f"ERROR - Could not find lat/long for {property['title']} via setView")
                    pass

        if ('lat' not in property) or ('lon' not in property):
            log(f"ERROR - Could not find lat/long for {property['title']}")
            # property = geocode_property(property)
        else:
            log(f"Found lat/long for {property['title']}: {property['lat']}, {property['lon']}")


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

class oakmans():
    def __init__(self) -> None:
        self.BASE_LINK = f"https://oakmans.co.uk/buying/?department=student"
        self.properties = []

        soup = BeautifulSoup(get(self.BASE_LINK).text, features="lxml")
        try:
            self.pages = soup.find('ul', class_='pagination').find_all('li')[-2].text
        except:
            raise Exception("Could not find pages for Oakmans")


    def find_first(self):
        current_page = 1
        url = f"https://oakmans.co.uk/buying/page/{current_page}/?department=student"

        self.get_page_info(url)

    def find_all(self):
        for i in range(1, int(self.pages) + 1):
            url = f"https://oakmans.co.uk/buying/page/{i}/?department=student"
            self.get_page_info(url, id=i,pages=int(self.pages))
        

    def save_to_json(self):
        with open('oakmans.json', 'w') as f:
            json.dump(self.properties, f, sort_keys=True, indent=4)

    def get_page_info(self, url, id=0, pages=0):
        soup = BeautifulSoup(get(url).text, features="lxml")

        log(f"[OAKMANS] [{id}/{pages}] Oakmans - Getting page info from... {url}")

        properties_raw = soup.find('div', class_='properties card-deck')
        properties_raw = properties_raw.find_all('a')

        for index, property_raw in enumerate(properties_raw):
            property = {}


            property['source'] = "Oakmans"
            property['url'] = property_raw['href']
            property['title'] = property_raw.find('h3', class_='card-header').text.split('£')[0].strip()
            log(f"[OAKMANS] Getting basic data about... {property['title']}")
            property['price'] = property_raw.find('small').text.strip()

            property['price'] = property['price'].replace('per person per week', 'pppw')

            property['beds'] = property_raw.find('p', class_='card-text').text.split(' ')[0].strip()

            property = self.get_property_info(property['url'], property, id=index, total=len(properties_raw))

            self.properties.append(property)

    def get_property_info(self, url, property, id=0, total=0):
        soup = BeautifulSoup(get(url).text, features="lxml")

        log(f"[OAKMANS] [{id}/{total}] Getting more data about... {property['title']}")

        lat_lng = soup.find_all('script')[-4].text.split('\n')[7].split('LatLng(')[1].split(')')[0].split(',')
        property['lat'] = lat_lng[0].strip()
        property['lon'] = lat_lng[1].strip()

        property['available_date'] = "Unknown"
        features = soup.find('h4', text='Description').find_next('p').text
        features_split = features.split(' – ')

        try:
            if "bathroom" in features.lower():
                property['baths'] = '1'
            elif "en suite" in features.lower() or "ensuite" in features.lower() or "en-suite" in features.lower() or "en suites" in features.lower():
                property['baths'] = property['beds']
            else:
                raw_baths = features_split[3].split(' ')[0].lower()
                if raw_baths == "one":
                    property['baths'] = '1'
                elif raw_baths == "two":
                    property['baths'] = '2'
                elif raw_baths == "three":
                    property['baths'] = '3'
                elif raw_baths == "four":
                    property['baths'] = '4'
                elif raw_baths == "five":
                    property['baths'] = '5'
                elif raw_baths == "six":
                    property['baths'] = '6'
                else:
                    property['baths'] = 'Unknown'
        except:
            log(f"ERROR - Could not find baths for {property['title']}")
            property['baths'] = "Unknown"

        return property
    
class purple_frog():
    def __init__(self) -> None:

        self.properties = []
        self.BASE_LINK = "https://www.purplefrogproperty.com/student-accommodation/Birmingham/?bills=&price%5Bfrom%5D=85&price%5Bto%5D=220&doubles%5Bfrom%5D=0&doubles%5Bto%5D=8&showers%5Bfrom%5D=1&showers%5Bto%5D=8&wc%5Bfrom%5D=1&wc%5Bto%5D=8&drawn=&year=next&sort=price-low&features=&view=grid"
        
        soup = BeautifulSoup(get(self.BASE_LINK).text, features="lxml")

        self.pages = soup.find('ul', class_='pagination').find_all('li', class_="page")[-3].text
    
    def find_first(self):
        self.get_page_info(self.BASE_LINK)

    def find_all(self):
        pass

    def save_to_json(self):
        with open('purple_frog.json', 'w') as f:
            json.dump(self.properties, f, sort_keys=True, indent=4)

    def get_page_info(self, url):
        soup = BeautifulSoup(get(url).text, features="lxml")

        properties_raw = soup.find_all('div', class_='housing')
        
        for property_raw in properties_raw:
            property = {}

            property["title"] = property_raw.find('a', class_="url permalink summary adr").text
            property["url"] = "https://www.purplefrogproperty.com" + property_raw.find('a', class_="url permalink summary adr")['href']
            property["price"] = property_raw.find('div', class_="price rent").text.strip()

            property_raw_features = property_raw.find('footer', class_="description").find('ul').find_all('li')
            property['beds'] = property_raw_features[1].text.split(' ')[0].strip()

            if property['beds'] == "Share":
                property['beds'] = "Unknown"

            property['baths'] = property_raw_features[2].text.split(' ')[0].strip()
            log(f"[PURPLE FROG] Getting basic data about... {property['title']}")
            
            self.properties.append(property)


    def get_property_info(self, url, property):
        pass

class king_co():
    def __init__(self):
        self.BASE_LINK = "https://www.kingandcoproperties.com/search.ljson?channel=lettings&fragment=page-1"
        self.properties = []

        first_page = get(self.BASE_LINK).json()
        total_properties = first_page['pagination']["total_count"]

        self.pages = int(total_properties / 12) + 1

    def find_all(self):
        for i in range(1, self.pages + 1):
            self.get_page_info(f"https://www.kingandcoproperties.com/search.ljson?channel=lettings&fragment=page-{i}")
    def find_first(self):
        self.get_page_info(self.BASE_LINK)
    
    def get_page_info(self, url):
        log(f"[KING & CO] Getting page info from... {url}")

        page = get(url).json()

        for property in page['properties']:
            property = self.get_property_info(property)
            self.properties.append(property)
    
    def get_property_info(self, property_raw):
        property = {}

        property["title"] = property_raw['display_address']
        property["url"] = "https://www.kingandcoproperties.com" + property_raw['property_url']
        property["lat"] = property_raw['lat']
        property["lon"] = property_raw['lng']
        property["price"] = property_raw['price']

        property['beds'] = property_raw['bedrooms']
        property['baths'] = property_raw['bathrooms']
        property['receptions'] = property_raw['reception_rooms']
        property['source'] = "King & Co"

        return property
    def save_to_json(self):
        with open('king_co.json', 'w') as f:
            json.dump(self.properties, f, sort_keys=True, indent=4)

class direct_housing():
    def __init__(self):
        self.BASE_LINK = ("https://direct-housing.co.uk/property-search/page/", "/?orderby=price-asc&address_keyword&radius=1&department=residential-lettings&_let_type=Student&property_type&bedrooms&minimum_price&maximum_price&minimum_rent&maximum_rent&commercial_property_type&commercial_for_sale_to_rent&commercial_minimum_price&commercial_maximum_price&commercial_minimum_rent&commercial_maximum_rent&lat&lng")
        self.properties = []
        
        self.pages = self.max_pages()
        log(f"[DIRECT HOUSING] Found {self.pages} pages")
    
    def max_pages(self):
        soup = BeautifulSoup(get(self.build_url_by_page(1)).text, features="lxml")
        pages = soup.find('div', class_='propertyhive-pagination').find_all('a')[-2].text.strip()
        return int(pages)
    
    def reprocess_properties(self):
        new_properties = []
        for index, property in enumerate(self.properties):
            log(f"[DIRECT HOUSING] [{index}/{len(self.properties)}] Getting more data about... {property['title']}")
            property = self.get_property_info(property)
            new_properties.append(property)
        self.properties = new_properties

    def build_url_by_page(self, page):
        return self.BASE_LINK[0] + str(page) + self.BASE_LINK[1]

    def find_first(self):
        self.get_page_info(self.build_url_by_page(1))
        self.reprocess_properties()
    
    def find_all(self):
        for i in range(1, self.pages + 1):
            self.get_page_info(self.build_url_by_page(i))
        self.reprocess_properties()

    def get_page_info(self, url):
        soup = BeautifulSoup(get(url).text, features="lxml")

        log(f"[DIRECT HOUSING] Getting page info from... {url}")

        properties_raw = soup.find_all('div', class_='details')
        log(len(properties_raw))

        for index, property_raw in enumerate(properties_raw):
            try:
                property = {}

                property['source'] = "Direct Housing"
                property['title'] = property_raw.find('h3').text.strip()
                log(f"[DIRECT HOUSING] Getting basic data about... {property['title']}")
                property['url'] = property_raw.find('a')['href']
                
                try:
                    property['price'] = property_raw.find('div', class_='price').text.strip()
                except:
                    property['price'] = "Unknown"
                
                try:
                    property['status'] = property_raw.find('div', class_='availability').text.strip()
                except:
                    property['status'] = "Unknown"

                if property['status'] == "Let Agreed":
                    property['status'] = "Let"
                # property['title'] = property_raw.find('h3').text.strip()
                # property['url'] = property_raw.find('a')['href']
                # property['price'] = property_raw.find('span', class_='propertyhive-price').text.strip()

                # property['beds'] = property_raw.find('span', class_='propertyhive-bedrooms').text.strip()
                # property['baths'] = property_raw.find('span', class_='propertyhive-bathrooms').text.strip()

                self.properties.append(property)
            except:
                log(f"ERROR - Could not find basic data about {index + 1}")
        
    
    def get_property_info(self, property):
        soup = BeautifulSoup(get(property["url"]).text, features="lxml")

        log(f"[DIRECT HOUSING] Getting more data about... {property['title']}")

        try:
            property["beds"] = soup.find('div', class_='elementor-widget-bedrooms').text.strip()
        except:
            property["beds"] = "Unknown"

        try:
            property["baths"] = soup.find('div', class_='elementor-widget-bathrooms').text.strip()
        except:
            property["baths"] = "Unknown"

        try:
            for script in soup.find_all('script', class_=None, id=None, type=None):
                try:
                    raw_lat_lng = script.text.split("google.maps.LatLng(")[1]
                    raw_lat_lng = raw_lat_lng.split(")")[0]
                    raw_lat_lng = raw_lat_lng.split(", ")
                    property['lat'] = raw_lat_lng[0].strip()
                    property['lon'] = raw_lat_lng[1].strip()
                except:
                    pass
        except:
            pass

        if 'lat' not in property or 'lon' not in property:
            log(f"ERROR - Could not find lat/long for {property['title']}")
            property['lat'] = "Unknown"
            property['lon'] = "Unknown"
        

        property['available_date'] = "Unknown"

        property['images'] = []

        # property['address'] = soup.find('input', id='propertyhive-address')['value']

        property['status'] = "Unknown"

        return property
    
    def save_to_json(self):
        with open('direct_housing.json', 'w') as f:
            json.dump(self.properties, f, sort_keys=True, indent=4)
    



def all():
    outputs = []
    
    x = house_hunt()
    y = easy_lettings()
    try:
        z = oakmans()
    except Exception as e:
        print("Could not find Oakmans")
        print(e)
        pass
    a = purple_frog()
    b = king_co()
    c = direct_housing()

    t1 = threading.Thread(target=x.find_all)
    t2 = threading.Thread(target=y.find_all)
    
    try:
        t3 = threading.Thread(target=z.find_all)
    except:
        pass
    t4 = threading.Thread(target=a.find_all)
    t5 = threading.Thread(target=b.find_all)
    t6 = threading.Thread(target=c.find_all)

    t1.start()
    t2.start()
    try:
        t3.start()
    except:
        pass
    t4.start()
    t5.start()

    try:
        t6.start()
    except:
        pass


    t1.join()
    t2.join()
    try:
        t3.join()
    except:
        pass
    t4.join()
    t5.join()

    try:
        t6.join()
    except:
        pass


    # x.find_all()
    # # x.find_first()
    x.save_to_json()
    outputs = outputs + x.properties

    # y.find_first()
    # y.find_all()
    y.save_to_json()
    outputs = outputs + y.properties

    # # z.find_first()
    # z.find_all()
    try:
        z.save_to_json()
        outputs = outputs + z.properties
    except:
        pass

    # a.find_first()
    # a.find_all()
    a.save_to_json()
    outputs = outputs + a.properties

    # b.find_first()
    # b.find_all()
    b.save_to_json()
    outputs = outputs + b.properties

    c.save_to_json()
    # c.find_first()
    # c.find_all()
    outputs = outputs + c.properties

    try:
        outputs = manual_checks(outputs)
    except:
        log(f"{COLOURS['FAIL']}ERROR{COLOURS['ENDC']} - Could not run manual checks")

    with open('combined.json', 'w') as f:
        json.dump(outputs, f, sort_keys=True, indent=4)

def post_check():
    with open('combined.json', 'r') as f:
        properties = json.load(f)

    no_lat_long = []
    sources = []

    for property in properties:
        if 'lat' not in property:
            log(f"ERROR - Could not find lat/long for {property['title']}")
            if property not in no_lat_long:
                no_lat_long.append(property)
        if 'lon' not in property:
            log(f"ERROR - Could not find lat/long for {property['title']}")
            if property not in no_lat_long:
                no_lat_long.append(property)

        if 'available_date' not in property:
            log(f"ERROR - Could not find available date for {property['title']}")
        if 'beds' not in property:
            log(f"ERROR - Could not find beds for {property['title']}")
        if 'baths' not in property:
            log(f"ERROR - Could not find baths for {property['title']}")
        if 'price' not in property:
            log(f"ERROR - Could not find price for {property['title']}")
        if 'source' not in property:
            log(f"ERROR - Could not find source for {property['title']}")
        else:
            if property['source'] not in sources:
                sources.append(property['source'])
    if len(no_lat_long) > 0 & len(properties) > 0:
        print(f"Found {len(no_lat_long)} ({int(len(no_lat_long)/len(properties) * 100)}%) properties with no lat/long:")
    for property in no_lat_long:
        print(f" - {property['title']} ({property['source']})")

def test_geocode(property={"title": "115 Tiverton Road", "source": "House Hunt"}):
    print(geocode_property(property))

def manual_checks(properties):
    edited_properties = []

    MANUAL_PROPERTIES = [
        {"title": "107 TIVERTON ROAD", "source": "King & Co"},
        {"title": "43 Alton Road", "source": "Easy Lettings"},
    ]
    
    for property in properties:
        if 'lat' not in property:
            property = geocode_property(property)
        if 'lon' not in property:
            property = geocode_property(property)
        if 'available_date' not in property:
            property['available_date'] = "Unknown"
        if 'beds' not in property:
            property['beds'] = "Unknown"
        if 'baths' not in property:
            property['baths'] = "Unknown"
        if 'price' not in property:
            property['price'] = "Unknown"
        if 'source' not in property:
            property['source'] = "Unknown"
        if 'images' not in property:
            property['images'] = []
        if 'status' not in property:
            property['status'] = "Unknown"
        if 'address' not in property:
            property['address'] = "Unknown"

        for manual_property in MANUAL_PROPERTIES:
            if manual_property['title'] == property['title']:
                property = geocode_property(property)

        edited_properties.append(property)

    return edited_properties

def dh():
    outputs = []
    dh_obj = direct_housing()
    dh_obj.find_all()
    outputs = outputs + dh_obj.properties
    # dh_obj.save_to_json()
    with open('combined.json', 'w') as f:
        json.dump(outputs, f, sort_keys=True, indent=4)
# dh()

all()
post_check()
# test_geocode({"title": "Renwick Apartments, Selly Oak, B29 7BL - Flat 303", "source": "House Hunt"})
# test_geocode({"title": "63 Bristol Road Birmingham", "source": "Easy Lettings"})
# test_geocode({"title": "107 TIVERTON ROAD", "source": "King & Co"})