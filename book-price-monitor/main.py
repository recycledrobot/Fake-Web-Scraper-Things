import requests
from bs4 import BeautifulSoup
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from dotenv import load_dotenv
import os
import schedule
import time

class BookPriceTracker:
    def __init__(self, config_file='config.json'):
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        self.email_config = {
            'server': os.getenv('EMAIL_SERVER'),
            'port': int(os.getenv('EMAIL_PORT')),
            'sender': os.getenv('SENDER_EMAIL'),
            'recipient': os.getenv('RECIPIENT_EMAIL'),
            'password': os.getenv('EMAIL_PASSWORD')
        }

        self.books = []

    def add_books(self, books_path):
        with open(books_path) as f:
            new_books = json.load(f)
            self.books.extend(new_books)

    def validate_books_input(self):
        if not self.books:
            raise ValueError("No books have been loaded")

        for i, book in enumerate(self.books):
            if 'slug' not in book or 'asking_price' not in book:
                raise ValueError(f"Book {i} missing required fields")

    def get_book_details(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'lxml')

        title = soup.select_one('.product_main h1').text.strip()
        price = float(soup.select_one('p.price_color').text.strip()[1:])
        in_stock = 'in stock' in soup.select_one('p.availability').text.lower()

        return title, price, in_stock

    def notify(self, books_to_buy):
        msg = MIMEMultipart()
        msg['From'] = self.email_config['sender']
        msg['To'] = self.email_config['recipient']
        msg['Subject'] = self.config['email_subject']

        body_parts = []
        for i, book in enumerate(books_to_buy):
            body_parts.append(
                f"Title: {book['title']}\n"
                f"Current Price: £{book['price']}\n"
                f"Target Price: £{book.get('asking_price', 'N/A')}\n"
                f"Price Difference: £{book['asking_price'] - book['price']:.2f} below target\n"
                f"URL: {book['url']}\n"
            )
            if len(books_to_buy) > 1 and i < len(books_to_buy) - 1:
                body_parts.append("-------------------\n")


        summary = (
            f"Books Found: {len(books_to_buy)}\n"
            f"Potential Savings: £{sum(book['asking_price'] - book['price'] for book in books_to_buy):.2f}\n"
            f"\n-------------------\n"
        )

        full_body = summary + "\n" + "\n".join(body_parts)
        msg.attach(MIMEText(full_body, 'plain'))

        with smtplib.SMTP(self.email_config['server'], self.email_config['port']) as server:
            server.starttls()
            server.login(self.email_config['sender'], self.email_config['password'])
            server.send_message(msg)

    def check_books(self):
        self.validate_books_input()

        books_to_buy = []
        for book in self.books:
            full_url = f"{self.config['base_url']}{book['slug']}"
            title, price, in_stock = self.get_book_details(full_url)

            if in_stock and price <= book['asking_price']:
                book_info = {
                    'title': title,
                    'price': price,
                    'url': full_url,
                    'asking_price': book['asking_price']
                }
                books_to_buy.append(book_info)

        if books_to_buy:
            self.notify(books_to_buy)
            print(f'Found {len(books_to_buy)} books below asking price')

    def run(self):
        print("Initial check...")
        self.check_books()

        schedule.every(self.config['check_interval']).hours.do(self.check_books)
        print(f"Scheduler started - checking every {self.config['check_interval']} hours")

        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    load_dotenv()
    tracker = BookPriceTracker()
    tracker.add_books('books.json')
    #tracker.add_books('books2.json')
    tracker.run()

if __name__ == '__main__':
    main()
