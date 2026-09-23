# OKEY Kaspi review count

Once a day GitHub Actions reads the public review statistics of the OKEY product
card on Kaspi.kz and stores them in `kaspi-reviews.json`
(`{"total", "rating", "updatedAt"}`). The okeystaydry.com server downloads this file,
because Kaspi does not answer requests from the hosting provider's IP range.
