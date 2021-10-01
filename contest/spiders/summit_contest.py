import json
import logging

from scrapy import Spider

logger = logging.getLogger()


class SummitContest(Spider):
    name = "summit_contest"
    allowed_domains = ["contest-646508-5umjfyjn4a-ue.a.run.app"]
    start_urls = ["https://contest-646508-5umjfyjn4a-ue.a.run.app/listing"]

    def parse(self, response):
        page_links = response.css("div.item a[href*=listing\/i\/]")
        yield from response.follow_all(page_links, self.parse_item)

        pagination_links = response.css("div.item a[href*=page\=]")
        yield from response.follow_all(pagination_links, self.parse)

    def parse_item(self, response):
        def extract_with_css(query):
            return response.css(query).get(default="").strip()

        def extract_with_xpath(query):
            return response.xpath(query).get(default="").strip()

        item_id = extract_with_css("span#uuid::text")
        name = extract_with_css("div.content.second-content h2::text")
        image_id = response.css(
            "div.content.second-content div.right-image img::attr(src)"
        ).re_first(".*/(.*).jpg")

        image_id_script = response.xpath("//script[contains(text(),'iid')]").re_first(
            "const\s*iid\s*=\s*'([^']+)'"
        )

        image_id = image_id if image_id else image_id_script

        flavor = extract_with_xpath("//p[contains(text(),'Flavor:')]/span/text()")
        if "NO FLAVOR" in flavor:
            flavor_link = extract_with_css("span.flavor::attr(data-flavor)")
            if flavor_link:
                yield response.follow(
                    flavor_link,
                    callback=self.parse_flavor,
                    errback=self.recover_item,
                    cb_kwargs=dict(
                        item_id=item_id,
                        name=name,
                        image_id=image_id,
                        flavor=flavor,
                    ),
                )
        else:
            yield {
                "item_id": item_id,
                "name": name,
                "image_id": image_id,
                "flavor": flavor,
            }

        recommended_links = response.css("div.main-btn a")
        yield from response.follow_all(recommended_links, self.parse_item)

    def parse_flavor(self, response, item_id, name, image_id, flavor):
        logger.info(f"Parsing flavor for {item_id!r}")
        json_response = json.loads(response.text)
        flavor_new = json_response.get("value", "")
        return {
            "item_id": item_id,
            "name": name,
            "image_id": image_id,
            "flavor": flavor_new if flavor_new else flavor,
        }

    def recover_item(self, failure):
        req_url = failure.request.url
        item = failure.request.cb_kwargs
        logger.warning(
            f"Errback was called while processing {req_url}. Recovered the data."
        )
        return item
