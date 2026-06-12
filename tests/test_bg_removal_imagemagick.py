from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from pix.contact_sheet import remove_green_screen
from pix.pixelize.bg_removal import (
    RemovalConfig,
    apply_imagemagick_fuzz_floodfill_alpha,
    remove_background,
    remove_background_with_result,
)


class PixelBgBackgroundRemovalTests(unittest.TestCase):
    def test_pixel_bg_method_makes_near_background_transparent(self) -> None:
        image = Image.new("RGBA", (5, 5), (250, 250, 250, 255))
        image.putpixel((2, 2), (20, 40, 200, 255))

        out = apply_imagemagick_fuzz_floodfill_alpha(image, key_rgb=(255, 255, 255), tolerance=5)
        alpha = np.asarray(out)[..., 3]

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[4, 4]), 0)
        self.assertEqual(int(alpha[2, 2]), 255)

    def test_enclosed_key_background_removed_by_default(self) -> None:
        image = Image.new("RGBA", (7, 7), (255, 255, 255, 255))
        for x in range(2, 5):
            image.putpixel((x, 2), (0, 0, 0, 255))
            image.putpixel((x, 4), (0, 0, 0, 255))
        for y in range(2, 5):
            image.putpixel((2, y), (0, 0, 0, 255))
            image.putpixel((4, y), (0, 0, 0, 255))
        image.putpixel((3, 3), (255, 255, 255, 255))

        out = apply_imagemagick_fuzz_floodfill_alpha(image, key_rgb=(255, 255, 255), tolerance=0)
        rgba = np.asarray(out)

        self.assertEqual(int(rgba[0, 0, 3]), 0)
        self.assertEqual(int(rgba[3, 3, 3]), 0)
        self.assertEqual(int(rgba[2, 2, 3]), 255)

    def test_enclosed_key_background_can_be_kept_for_compatibility(self) -> None:
        image = Image.new("RGBA", (7, 7), (255, 255, 255, 255))
        for x in range(2, 5):
            image.putpixel((x, 2), (0, 0, 0, 255))
            image.putpixel((x, 4), (0, 0, 0, 255))
        for y in range(2, 5):
            image.putpixel((2, y), (0, 0, 0, 255))
            image.putpixel((4, y), (0, 0, 0, 255))
        image.putpixel((3, 3), (255, 255, 255, 255))

        res = remove_background_with_result(
            image,
            RemovalConfig(
                t_core=0.5,
                t_grow=0.51,
                bg_color=(255, 255, 255),
                remove_enclosed_background=False,
                enforce_uniformity_guard=False,
            ),
        )
        rgba = np.asarray(res.image)

        self.assertEqual(res.confidence, "high")
        self.assertEqual(int(rgba[0, 0, 3]), 0)
        self.assertEqual(int(rgba[3, 3, 3]), 255)
        self.assertEqual(int(rgba[2, 2, 3]), 255)

    def test_remove_background_uses_reference_pixel_bg_algorithm(self) -> None:
        image = Image.new("RGBA", (5, 5), (240, 240, 240, 255))
        image.putpixel((2, 2), (220, 20, 20, 255))

        out = remove_background(image, tolerance=4, bg_removal_algorithm="auto")
        alpha = np.asarray(out)[..., 3]

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[2, 2]), 255)

    def test_remove_green_screen_uses_explicit_key_color(self) -> None:
        image = Image.new("RGBA", (7, 7), (0, 255, 0, 255))
        image.putpixel((0, 0), (0, 0, 0, 255))
        image.putpixel((3, 3), (30, 60, 200, 255))

        out, bbox = remove_green_screen(
            image,
            green_rgb=(0, 255, 0),
            tolerance=0,
            crop_padding=0,
            crop_square=False,
        )
        rgba = np.asarray(out.convert("RGBA"))
        opaque_green = (rgba[..., 3] > 0) & (rgba[..., 0] == 0) & (rgba[..., 1] == 255) & (rgba[..., 2] == 0)

        self.assertIsNotNone(bbox)
        self.assertFalse(bool(opaque_green.any()))
        self.assertTrue(bool(((rgba[..., 3] > 0) & (rgba[..., 2] == 200)).any()))

    def test_existing_transparent_border_does_not_delete_black_subject(self) -> None:
        image = Image.new("RGBA", (7, 7), (0, 0, 0, 0))
        for y in range(2, 5):
            for x in range(2, 5):
                image.putpixel((x, y), (0, 0, 0, 255))

        out = remove_background(image, tolerance=26, bg_removal_algorithm="pixel_bg")
        alpha = np.asarray(out)[..., 3]

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[3, 3]), 255)

    def test_existing_transparent_border_does_not_delete_black_subject_touching_edge(self) -> None:
        image = Image.new("RGBA", (7, 7), (0, 0, 0, 0))
        for y in range(0, 5):
            image.putpixel((3, y), (0, 0, 0, 255))
        for x in range(2, 5):
            image.putpixel((x, 4), (0, 0, 0, 255))

        out = remove_background(image, tolerance=26, bg_removal_algorithm="pixel_bg")
        alpha = np.asarray(out)[..., 3]

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[0, 3]), 255)
        self.assertEqual(int(alpha[4, 3]), 255)

    def test_uniformity_guard_returns_original_for_non_key_image(self) -> None:
        rng = np.random.RandomState(2)
        arr = rng.randint(0, 256, (40, 40, 3)).astype(np.uint8)
        image = Image.fromarray(arr, "RGB")

        res = remove_background_with_result(image)
        out = np.asarray(res.image.convert("RGB"))

        self.assertEqual(res.confidence, "low")
        self.assertTrue(np.array_equal(out, arr))

    def test_legacy_color_to_alpha_option_is_compatible(self) -> None:
        image = Image.new("RGBA", (5, 5), (255, 255, 255, 255))
        image.putpixel((2, 2), (0, 0, 0, 255))

        out = remove_background(image, tolerance=0, bg_removal_algorithm="color_to_alpha")
        alpha = np.asarray(out)[..., 3]

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[2, 2]), 255)


if __name__ == "__main__":
    unittest.main()
