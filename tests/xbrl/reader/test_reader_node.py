import os
import shutil
import unittest
from xbrr.xbrl.reader.reader import Node
from xbrr.xbrl.reader.element_schema import ElementSchema

class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        p1 = ElementSchema("parent1", "", "label_parent1")
        self.parent1 = Node(p1)
        p2 = ElementSchema("parent2", "", "label_parent2")
        self.parent2 = Node(p2)
        c1 = ElementSchema("child1", "", "label_child1")
        self.child1 = Node(c1)
        c2 = ElementSchema("child2", "", "label_child2")
        self.child2 = Node(c2)

    def test_add_parent1(self):
        "add parent and add parent override"
        self.assertTrue(self.parent1.is_leaf)
        self.assertTrue(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'', 'priority':0, 'order':1})
        self.assertFalse(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, '', '1', '2')
        self.assertEqual(len(self.child1.plinks.src), 2, "after adding second parent")
        self.assertDictEqual(self.child1.plinks.src[1].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'', 'priority':1, 'order':2})
        self.assertFalse(self.parent1.is_leaf)

    def test_add_parent2(self):
        "add parent1 and add parent2 and add prent1 prohibited"
        self.assertTrue(self.parent1.is_leaf)
        self.assertTrue(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'', 'priority':0, 'order':1})
        self.assertFalse(self.parent1.is_leaf)
        self.assertTrue(self.parent2.is_leaf)

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.plinks.active_src), 2)
        self.assertDictEqual(self.child1.plinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'use':'', 'priority':0, 'order':2})
        self.assertFalse(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 2, "not delete parent1 due to the same priority")
        self.assertFalse(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "delete parent1 due to the higher priority")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'deleted', 'priority':1, 'order':1})
        self.assertTrue(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

    def test_add_parent3(self):
        "add parent1 prohibited and add parent1 and parent2"
        self.assertTrue(self.parent1.is_leaf)
        self.assertTrue(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 0, "prohibited link hos no count")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'prohibited', 'priority':1, 'order':1})
        self.assertTrue(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 0, "deleted link hos no count")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'deleted', 'priority':1, 'order':1})
        self.assertTrue(self.parent1.is_leaf)

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "deleted link and active link")
        self.assertDictEqual(self.child1.plinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'use':'', 'priority':0, 'order':2})
        self.assertTrue(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

    def test_add_parent4(self):
        "add parent1 prohibited and add parent2 and add prent1"
        self.assertTrue(self.parent1.is_leaf)
        self.assertTrue(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'prohibited', 'priority':1, 'order':1})

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "protected link and active link")
        self.assertDictEqual(self.child1.plinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'use':'', 'priority':0, 'order':2})
        self.assertTrue(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "deleted link and active link")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'deleted', 'priority':1, 'order':1})
        self.assertTrue(self.parent1.is_leaf)
        self.assertFalse(self.parent2.is_leaf)

    def test_add_parent5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.assertTrue(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "one active link")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'', 'priority':0, 'order':1})
        self.assertFalse(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.plinks.active_src), 2, "two active link with different orders")
        self.assertDictEqual(self.child1.plinks.src[1].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'', 'priority':0, 'order':2})
        self.assertFalse(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 2, "not delete parent 1 due to the same priority")
        self.assertFalse(self.parent1.is_leaf)

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.plinks.active_src), 1, "active link and deleted link")
        self.assertDictEqual(self.child1.plinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'use':'deleted', 'priority':1, 'order':1})
        self.assertFalse(self.parent1.is_leaf)



    def test_add_derive1(self):
        "add parent and add parent override"
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':0, 'order':1, 'use':'', 'weight':1})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, '', '1', '2', '2.0')
        self.assertEqual(len(self.child1.clinks.src), 2, "after adding second parent")
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())

    def test_add_derive2(self):
        "add parent1 and add parent2 and add prent1 prohibited"
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':0, 'order':1, 'use':'', 'weight':1})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, 'prohibited', '1', '1', '1.5')
        self.assertEqual(len(self.child1.clinks.src), 1)
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'deleted', 'weight':1.5})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent2, '', '0', '2.0', '2.0')  # order 2.0
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'priority':0, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertTrue(self.parent2.has_derived())

        self.child1._add_derive(self.parent2, 'prohibited', '1', '2', '1.6') # order 2 matches with order 2.0
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'priority':1, 'order':2, 'use':'deleted', 'weight':1.6})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

    def test_add_derive3(self):
        "add parent1 prohibited and add parent1 and parent2"
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'prohibited', 'weight':1})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '1', '1.5')
        self.assertEqual(len(self.child1.clinks.src), 1)
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'deleted', 'weight':1})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent2, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'priority':0, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertTrue(self.parent2.has_derived())

    def test_add_derive4(self):
        "add parent1 prohibited and add parent2 and add prent1"
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'prohibited', 'weight':1})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertFalse(self.parent2.has_derived())

        self.child1._add_derive(self.parent2, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'priority':0, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertTrue(self.parent2.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '1', '1.5')
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'deleted', 'weight':1})
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent2', 'to':'child1', 'priority':0, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())
        self.assertTrue(self.parent2.has_derived())

    def test_add_derive5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':0, 'order':1, 'use':'', 'weight':1})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':0, 'order':1, 'use':'', 'weight':1})
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':0, 'order':2, 'use':'', 'weight':2})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, 'prohibited', '1', '1', '1.5')
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[0].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':1, 'use':'deleted', 'weight':1.5})
        self.assertFalse(self.child1.no_derive())
        self.assertTrue(self.parent1.has_derived())

        self.child1._add_derive(self.parent1, 'prohibited', '1', '2', '1.6') # cares the orde, not cares the weight
        self.assertEqual(len(self.child1.clinks.src), 2)
        self.assertDictEqual(self.child1.clinks.src[1].to_dict(),
                             {'from':'parent1', 'to':'child1', 'priority':1, 'order':2, 'use':'deleted', 'weight':1.6})
        self.assertTrue(self.child1.no_derive())
        self.assertFalse(self.parent1.has_derived())

