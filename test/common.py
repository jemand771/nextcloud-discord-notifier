from parameterized import parameterized


def expand_single(iterator):
    return parameterized.expand((x,) for x in iterator)


def flatten(some_list):
    return [inner_element for inner_list in some_list for inner_element in inner_list]
