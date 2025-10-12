import time
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from services.base import Service
from models import Container, TelegramChannel

class WebParserService(Service):

    def __init__(self):
        super().__init__()

        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # если нужно без GUI
        # chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--no-sandbox")

        # Selenium сам найдет подходящий драйвер
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    async def run(self, url: str) -> Container:
        self.driver.get(url)
        results = []

        main_block = self.driver.find_element(By.ID, "block-a745004724d64e14a80cde8903f35b13")
        main_block.click()
                
        time.sleep(0.2)

        # Находим все toggle-блоки внутри
        list_div = self.driver.find_element(By.CLASS_NAME, "notion-toggle__content")
        
        for toggle in list_div.find_elements(By.CLASS_NAME, "notion-toggle"):
            try:
                # Кликаем по summary, чтобы открыть toggle
                summary = toggle.find_element(By.CLASS_NAME, "notion-toggle__summary")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", summary)
                summary.click()
                time.sleep(0.2)

                city = summary.text.strip()
                
                # Контент с ссылками
                content = toggle.find_element(By.CLASS_NAME, "notion-toggle__content")
                links = content.find_elements(By.TAG_NAME, "a")
                
                for a in links:
                    href = a.get_attribute("href")
                    if href and "t.me" in href:
                        results.append(
                            TelegramChannel(
                                city=city.replace("‣", "").replace("\n", "").strip(),
                                name=a.text.strip(),
                                url=href
                            )
                        )
            except Exception as e:
                print(f"Ошибка при обработке toggle: {e}")
                continue
        
        self.driver.quit()
        return Container(channels = results)