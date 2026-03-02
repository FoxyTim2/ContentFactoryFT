import unittest

from newsbot.llm import NoOpContentProcessor


class NoOpContentProcessorTests(unittest.TestCase):
    def test_detects_russia_topic(self):
        processor = NoOpContentProcessor()
        result = processor.process_message('Новости РФ и Москва сегодня')
        self.assertEqual('russia', result.topic)

    def test_non_ru_goes_to_review(self):
        processor = NoOpContentProcessor()
        result = processor.process_message('Breaking news in english only')
        self.assertEqual('review', result.action)

    def test_ads_are_stripped(self):
        processor = NoOpContentProcessor()
        result = processor.process_message('Купить сейчас! Промокод TEST. Подписывайтесь!')
        self.assertNotIn('Промокод', result.ru_text)


if __name__ == '__main__':
    unittest.main()
