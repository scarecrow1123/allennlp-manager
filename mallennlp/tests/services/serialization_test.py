from typing import List

from mallennlp.services.serialization import serializable, serialize, deserialize


@serializable
class Inner:
    x: str
    _y: str


@serializable
class Outer:
    a: int
    b: Inner
    c: List[Inner]


def test_encode_and_decode():
    o = Outer(1, Inner(x="1", y="2"), [Inner("3", "4")])
    assert o.a == 1
    assert o.b.x == "1"
    assert o.b._y == "2"
    s = serialize(o)  # type: ignore
    assert deserialize(Outer, s) == o  # type: ignore
