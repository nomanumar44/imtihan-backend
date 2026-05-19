import scrapy


class MCQItem(scrapy.Item):
    question    = scrapy.Field()
    option_a    = scrapy.Field()
    option_b    = scrapy.Field()
    option_c    = scrapy.Field()
    correct     = scrapy.Field()
    explanation = scrapy.Field()
    exam_slug   = scrapy.Field()
    subject_slug = scrapy.Field()
    source_url  = scrapy.Field()
    paper_title = scrapy.Field()
    paper_url   = scrapy.Field()
    paper_year  = scrapy.Field()
