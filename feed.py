class Feed:
    def __init__(self, source):
        self.source = source

    def _update_submissions(self, timestamp):
        raise NotImplementedError

    def _update_images(self):
        """
        1. Get all in submissions
        2. Parse each link
        3. Download each image and convert it
        """
        raise NotImplementedError

    def _update_4histogram(self):
        """
        4. Process image into histograms
        5. Insert data into 4histogram
        """
        pass

    def _update_dhash(self):
        """
        4. Process image into histograms
        5. Insert data into dhash
        """
        pass


