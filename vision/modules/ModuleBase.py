import numpy as np

class _PsuedoOptionsDict:
    def __init__(self, options_dict):
        self._options_dict = options_dict

    def __getitem__(self, name):
        return self._options_dict[name].value

    def __setitem__(self, name, value):
        self._options_dict[name].update(value)

class ModuleBase:
    def __init__(self, options=None, order_post_by_time=True):
        self.acq_time = -1
        self.order_post_by_time = order_post_by_time
        self.posted_images = []

        if options is None:
            options = []

        self.options_dict = {option.name: option for option in options}
        self._psuedo_options = _PsuedoOptionsDict(self.options_dict)

    def post(self, tag, image):
        image = np.ascontiguousarray(image)
        if self.order_post_by_time:
            self.posted_images.append((tag, image))
        else:
            i = 0
            while i < len(self.posted_images) and self.posted_images[i][0] < tag:
                i += 1
            self.posted_images.insert(i, (tag, image))

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        elif item == 'options':
            return self._psuedo_options
        else:
            raise AttributeError()
