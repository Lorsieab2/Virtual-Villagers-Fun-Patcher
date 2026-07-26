from __future__ import annotations

import unittest

from tools.vv1_parentage_log import BirthCard, Person, render_parentage_html


class VV1ParentageLogTests(unittest.TestCase):
    def test_html_reports_requested_strings_and_numeric_fields(self) -> None:
        mother = Person("Mother <A>", 1, 2, 3)
        father = Person("Father & B", 2, 4, 12)
        child = Person(
            "Child",
            2,
            6,
            15,
            likes=("Running",),
            dislikes=("Mushrooms",),
            skills={"Parenting": 7, "Building": 8, "Farming": 9, "Healing": 10, "Research": 11},
        )
        html = render_parentage_html(
            [BirthCard(child, mother, father)],
            game_title="Virtual Villagers - The Secret City",
        )
        self.assertIn(
            "head and body values correspond to the rows in the Body and Head pictures in the Images folder.",
            html,
        )
        self.assertIn("The Secret City Parentage Log", html)
        self.assertIn("Child", html)
        self.assertIn("Mother &lt;A&gt;", html)
        self.assertIn("Father &amp; B", html)
        self.assertIn("Head: 6", html)
        self.assertIn("Body: 15", html)
        self.assertIn("Likes:</b> Running", html)
        self.assertIn("Dislikes:</b> Mushrooms", html)
        self.assertIn("Parenting: 7", html)
        self.assertIn("female_heads.png", html)
        self.assertIn("male_heads.png", html)
        self.assertIn("male_bodies10.png", html)

    def test_html_scales_past_stock_and_expanded_population_sizes(self) -> None:
        person = Person("Villager", 1, 0, 0, skills={})
        cards = [BirthCard(Person(f"Child {i}", 1, i % 20, i % 20), person, person) for i in range(512)]
        html = render_parentage_html(cards)
        self.assertEqual(html.count('class="birth-card"'), 512)
        self.assertIn("Child 511", html)

    def test_embedded_sprite_data_is_supported(self) -> None:
        person = Person("Villager", 1, 0, 0)
        html = render_parentage_html(
            [BirthCard(person, person, person)],
            image_data={
                "female_heads.png": b"head",
                "female_bodies00.png": b"body",
            },
        )
        self.assertIn("data:image/png;base64,aGVhZA==", html)
        self.assertIn("data:image/png;base64,Ym9keQ==", html)


if __name__ == "__main__":
    unittest.main()
