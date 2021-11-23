import scrapy
from copy import deepcopy
import re
import json
import time
from douban_book.items import DoubanBookItem


class BookSpider(scrapy.Spider):
    name = 'book'
    allowed_domains = ['book.douban.com']
    start_urls = ['https://book.douban.com/tag/?view=type&icn=index-sorttags-all']

    def parse(self, response, **kwargs):
        category_list = response.xpath("//div[@class='article']//tbody//td/a/text()").extract()
        # 遍历所有分类，每个分类下有1000条数据可爬取
        for category in category_list:
            for start in range(0, 1000, 20):
                url = f'https://book.douban.com/tag/{category}?start={start}'
                yield scrapy.Request(url=url, callback=self.parse_tag_page)

    def parse_tag_page(self, response):
        book_urls = response.xpath('//*[@id="subject_list"]/ul/li/div[2]/h2/a/@href').extract()
        for url in book_urls:
            yield scrapy.Request(url=url, callback=self.parse_detail_page)

    def parse_detail_page(self, response):
        item = DoubanBookItem()
        item['grab_url'] = response.url
        schema = response.xpath("//script[@type='application/ld+json']/text()").extract_first()
        if schema is not None:
            d = eval(schema)
            item['title'] = d.get('name')
            item['isbn13'] = d.get('isbn')
            try:
                author = d['author'][0].get('name')
            except IndexError:
                pass
            else:
                item['author'] = author
        info = response.xpath("//div[@id='info']").extract_first()
        info_map = {
            '副标题': 'subtitle',
            '原作名': 'origin_title',
            '出版年': 'pubdate',
            '出版社': 'publisher',
            '页数': 'pages',
            '定价': 'price',
            '装帧': 'binding',
            '丛书': 'series',
        }
        for name, item_name in info_map.items():
            try:
                temp = re.search(rf'{name}:</span>(.*?)<br>', info)
            except:
                continue
            if temp is not None:
                item[item_name] = temp.group(1).strip()

        rating = response.xpath("//strong[@class='ll rating_num ']/text()").extract_first()
        if rating is not None:
            item['rating'] = rating.strip()
        #书籍封面
        item['image'] = response.xpath("//*[@id='mainpic']/a/@href").extract_first()
        #译者
        translator = response.xpath("//span[contains(text(),' 译者')]/../a/text()").extract()
        item["translator"] = ','.join(translator)

        #内容简介
        item['summary'] = response.xpath("//div[@id='link-report']//div[@class='intro']").extract_first('NULL')
        #作者简介
        item['author_intro'] = response.xpath(
            "//span[text()='作者简介']/../following-sibling::div[1]//div[@class='intro']").extract_first('NULL')
        
        if response.url is not None:
            book_id = re.search(r'(\d+)/$', response.url).group(1)
            #豆瓣id
            item['douban_id'] = book_id
            directory_list = response.xpath(f"//div[@id='dir_{book_id}_full']/text()").extract()
            item['catalog'] = ';'.join(directory_list)

        tags = response.xpath("//div[@id='db-tags-section']//a[@class='  tag']/text()").extract()
        item["tags"] = ','.join(tags)
        #采集时间
        item["grab_time"] = int(time.time())

        yield item

       

    def parse_review_page(self, response):
        review_item = DoubanBookReview()
        data = response.meta["data"]
        review_item['url'] = data['url']
        review_item['title'] = data['title']
        review = re.sub(r'<.*?>', ' ', json.loads(response.text)['html'])
        review_item['review'] = re.sub(r"--&gt;|\u3000|\n|\t|&nbsp;|&amp;|&quot;", " ", review).strip()
        yield review_item


if __name__ == '__main__':
    from scrapy.cmdline import execute
    # cmd: scrapy crawl book
    execute(['scrapy', 'crawl', 'book'])