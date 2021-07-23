from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd
import regex as re


class AmazonScrapper:
    """
    This Program or Whatever you call it is a webscrapper for the Amazon website
    It searches and stores the products that fit in the following criteria:
    - Has only One Seller
    - Not in the blacklisted Brandlist given
    - BRN number within the range of 1 to 150,000

    """
    
    def __init__(self, base_url, paging_url, no_of_pages,
                 driver_path='C:/Users/Jimoh/Documents/ML projects/Scraping/chrome/chromedriver_win32/chromedriver.exe', 
                 brand_list_path = 'C:/Users/Jimoh/Documents/GitHub/Scraper/docs/brandList.csv'):
        
        """
        Here the paging url, first page url and number of pages the product search has are given
        The paths to the chrome driver and blacklisted brandlist is given
        
        """
        self.driver_path = driver_path
        self.brand_list_path = brand_list_path
        self.base_url = base_url
        self.no_of_pages = no_of_pages
        self.paging_url = paging_url
        self.proc_paging_url()
        
    def proc_paging_url(self):
        """
        The paging url is formatted so it can be reproducable for multiple pages
        
        """
        self.paging_url = self.paging_url.replace(re.findall('qid=\d+&*', self.paging_url)[0], '')
        self.paging_url = self.paging_url.replace(re.findall('page=\d', self.paging_url)[0], 'page={}')
        self.paging_url = self.paging_url.replace(re.findall('sr_pg_\d', self.paging_url)[0], 'sr_pg_{}')
    
    @property
    def brand_list(self):
        """
        Returns the Black listed brand lists
        
        """
        return pd.read_csv(self.brand_list_path).set_index('0')#.iloc[:,0].to_list()
        
    def get_paging_url(self, page_no):
        """
        Gets the paging url from the user
        
        """
        return self.paging_url.format(page_no, page_no)
    
    def set_src(self, page_no=1):
        """ 
        Sets the HTML source code of the page in class variabe src
        
        """
        options = Options()
        # connects the driver to the already opened browser with remote debugging
        options.add_experimental_option('debuggerAddress', 'localhost:9222')

        driver = webdriver.Chrome(options=options, executable_path=self.driver_path)
        if page_no == 1:
            driver.get(self.base_url)
        elif page_no > 1:
            driver.get(self.get_paging_url(page_no))
        
        self.src = bs(driver.page_source, features= 'html.parser')
        driver.quit()
    
    @property
    def product_panes(self):
        """
        Returns the product holders' source codes
        
        """
        product_panes = self.src.find_all('div', {'data-component-type':'s-search-result'})
        return product_panes

    def get_product_asin(self, product_pane):
        """
        Gets the product ASIN
        
        """
        return product_pane.attrs['data-asin']
            
        
    def get_product_desc(self, product_pane):
        """
        Gets the product description
        
        """    
        product_desc = product_pane.h2.a.text.strip()
        return product_desc
    
    def get_product_brand(self, product_pane):
        options = self.get_product_desc(product_pane).split()[:2]
        for i in options:
            try:
                int(i)
            except ValueError:
                brand = i.upper()
                break
        return brand
        
    def get_product_link(self, product_pane):
        """
        Gets the url link to the product
        
        """
        product_link = 'https://www.amazon.com' + product_pane.h2.a['href']
        return product_link
    
    def get_ccc_link(product_pane):
        f = 'https://charts.camelcamelcamel.com/us/{}/amazon.png?force=1&zero=0&w=594&h=356&desired=false&legend=1&ilt=1&tp={}&fo=1&lang=en'
        
        asin = self.get_product_asin(product_pane)
        all_ccc = f.format(asin, 'all')
        m_ccc = f.format(asin, '3m')
        
        return all_ccc, m_ccc
        
    
    def get_product_price(self, product_pane):
        """
        Gets the product price
        
        """
        try:
            product_price_pane = product_pane.find('span', 'a-price')
            product_price = float(product_price_pane.find('span', 'a-offscreen').text.strip().replace(',','')[1:])
            return product_price
        except AttributeError:
            return -1
        
    def get_helium_pane(self, product_pane):
        """
        Gets the src codes of the pane rendered by the helium 10 extension
        
        """
        helium_pane = product_pane.find('div', {'id':re.compile('bsr-\w+')}).div
        return helium_pane

    def filter_asin_by_disallowed_brands(self, product_pane):
        """
        filters the product by checking if it is not in the blacklisted brand list
        if it passes return 1, otherwise 0
        
        """
        brand = self.get_product_brand(product_pane)
        sub_brand_list = list(self.brand_list.filter(like= brand[:3], axis= 'index').index)

        for i in sub_brand_list:
            if brand[:-1] in i:
                return 0
        return 1
    
    def filter_asin_by_price(self, product_pane):
        """
        Filters the product the price
        
        """
        price = self.get_product_price(product_pane)
        if price == -1:
            return 0
        else:
            return 1

    def filter_asin_by_seller_count(self, product_pane, count = 1):
        """
        filters the product by making sure the number of sellers is less than the threshold given
        if it passes return 1, otherwise 0 (helium extension used)
        
        """
        try:
            helium_pane = self.get_helium_pane(product_pane)
            try:
                seller_count = helium_pane.findAll('div', recursive= False)[1].findAll('div')[1].findAll('a')[1].text.split(' ')[0].replace(',', '')
            except IndexError:
                print(IndexError)
                return 0
            
            if int(seller_count) > count:
                return 0
            else:
                return 1
        except err:
            print(f'filter_asin_by_seller_count ==> {err}')
            return 0

    def filter_asin_by_brn_no(self, product_pane):
        """
        filters the product by making sure it falls into the allowed range of brn numbers (1 - 150,000)
        if it passes return 1, otherwise 0 (helium extension used)
        """
        helium_pane = self.get_helium_pane(product_pane)
        brns= []
        for i in range(len(helium_pane.findAll('div', recursive= False)[0].findAll('div'))):
            brn_data = (helium_pane.findAll('div', recursive= False)[0].findAll('div')[i].text)
            try:
                brn_data = brn_data.split()[0][1:].replace(',','')
            except IndexError:
                print(IndexError)
                return 0
            try:
                if int(brn_data) > 150000:
                    return 0
                else:
                    brns.append(int(brn_data))
            except ValueError:
                return 0
        return 1
    
    def apply_filters_on_pane(self, product_pane):
        """
        Applies all the given filters on the product
        
        """
        result = []
        result.append(self.filter_asin_by_seller_count(product_pane))
        result.append(self.filter_asin_by_disallowed_brands(product_pane))
        result.append(self.filter_asin_by_brn_no(product_pane))
        result.append(self.filter_asin_by_price(product_pane))
        return result
    
    def apply_filters_on_page(self, product_panes):
        """
        Applies the filters on each product on the page and returns the qualified ones
        
        """
        valid_products = []
        for i in product_panes:
            filters = self.apply_filters_on_pane(i)
            if 0 not in filters:
                valid_products.append((self.get_product_asin(i), 
                                      self.get_product_desc(i),
                                      self.get_product_brand(i),
                                      self.get_product_link(i), 
                                      self.get_product_price(i),
                                      self.get_ccc_link(i)[0],
                                      self.get_ccc_link(i)[1]))
        return valid_products
    
    
    def scrape_pages(self, no_of_products= 42):
        """
        Getting the qualified products after applying filters for multiple pages
        
        """
        try:
            products = []
            for i in range(1, self.no_of_pages + 1):
                if i == 1:
                    self.set_src()
                elif i > 1: 
                    self.set_src(i)
                panes = self.product_panes
                product = self.apply_filters_on_page(panes)
                products += product
                print(f'Page {i} ==> {len(products)} product(s) found')

                if len(products) >= no_of_products:
                    break

            self.products_df = pd.DataFrame(products, columns=['ASIN', 'Description', 'Brand', 'Link', 'Price', 'Total Duration', '3 months Duration'])
            return self.products_df, i
        except KeyboardInterrupt:
            self.products_df = pd.DataFrame(products, columns=['ASIN', 'Description', 'Brand', 'Link', 'Price', 'Total Duration', '3 months Duration'])
            return self.products_df, i
    
     
    def save_result(self):
        self.products_df.to_excel('C:/Users/Jimoh/Documents/GitHub/Scraper/docs/products.xlsx', index= False)      
    
        
base = 'https://www.amazon.com/s?bbn=16225007011&dc&i=computers-intl-ship&k=-thfjfd%20keyboards&qid=1626710483&ref=glow_cls&refresh=1&rh=p_6%3AATVPDKIKX0DER%2Cp_36%3A2000-&rnid=386442011&s=relevancerank'

page = 'https://www.amazon.com/s?k=-thfjfd+keyboards&i=computers-intl-ship&bbn=16225007011&rh=p_6%3AATVPDKIKX0DER%2Cp_36%3A2000-&s=relevancerank&dc&page=2&qid=1626759178&refresh=1&rnid=386442011&ref=sr_pg_2'

scraper = AmazonScrapper(base, page, 105)
df, no_of_pages_scrapped = scraper.scrape_pages(200)

scraper.save_result()



