import unittest

from newsbot.llm import NoOpContentProcessor


class NoOpContentProcessorTests(unittest.TestCase):
    def test_prepare_adds_source_url(self):
        processor = NoOpContentProcessor()
        post = processor.prepare('Hello world', 'https://t.me/a/1')

        self.assertIn('Источник: https://t.me/a/1', post.body)
        self.assertEqual('Новость из отслеживаемого канала', post.title)

    def test_prepare_truncates_long_text(self):
        processor = NoOpContentProcessor()
        post = processor.prepare('x' * 1000, None)

        self.assertTrue(post.body.endswith('...'))
        self.assertLessEqual(len(post.body), 903)


if __name__ == '__main__':
    unittest.main()
