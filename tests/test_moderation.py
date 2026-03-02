import unittest

from newsbot.moderation import MarketingModerator, ModerationDecision, is_marketing


class _FakeClassifier:
    def __init__(self, result: ModerationDecision):
        self.result = result
        self.called = False

    def classify(self, text: str) -> ModerationDecision:
        self.called = True
        return self.result


class ModerationTests(unittest.TestCase):
    def test_fast_rules_marketing_for_cta(self):
        text = "Супер акция! Переходи по ссылке и купи курс со скидкой 50%"
        self.assertTrue(is_marketing(text))

    def test_fast_rules_non_marketing_news(self):
        text = "Правительство опубликовало новый отчет по экономике за квартал."
        self.assertFalse(is_marketing(text))

    def test_ambiguous_path_uses_llm_classifier(self):
        classifier = _FakeClassifier(
            ModerationDecision(is_marketing=True, reason="llm_detected_promo")
        )
        moderator = MarketingModerator(classifier=classifier)

        decision = moderator.is_marketing("Партнерский материал о новых возможностях платформы")

        self.assertTrue(classifier.called)
        self.assertTrue(decision.is_marketing)
        self.assertEqual(decision.reason, "llm_detected_promo")

    def test_ambiguous_path_accepts_non_marketing(self):
        classifier = _FakeClassifier(
            ModerationDecision(is_marketing=False, reason="llm_editorial_context")
        )
        moderator = MarketingModerator(classifier=classifier)

        decision = moderator.is_marketing("Материал при поддержке фонда о городских инициативах")

        self.assertFalse(decision.is_marketing)
        self.assertEqual(decision.reason, "llm_editorial_context")


if __name__ == '__main__':
    unittest.main()
