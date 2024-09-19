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
        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.add_parent(self.parent1, '', '1', '2')
        self.assertEqual(len(self.child1.parents), 2, "after adding second parent")
        self.assertDictEqual(self.child1.parents[1], {'parent':self.parent1, 'priority':'1', 'order':'2'})

    def test_add_parent2(self):
        "add parent1 and add parent2 and add prent1 prohibited"
        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 2)
        self.assertDictEqual(self.child1.parents[1], {'parent':self.parent2, 'priority':'0', 'order':'2'})

        self.child1.add_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.parents), 2, "not delete parent1 due to the same priority")

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.parents), 1, "not delete parent1 due to the same priority")
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent2, 'priority':'0', 'order':'2'})

    def test_add_parent3(self):
        "add parent1 prohibited and add parent1 and parent2"
        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'1', 'order':'1'})

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.parents), 0)

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent2, 'priority':'0', 'order':'2'})

    def test_add_parent4(self):
        "add parent1 prohibited and add parent2 and add prent1"
        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'1', 'order':'1'})

        self.child1.add_parent(self.parent2, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent2, 'priority':'0', 'order':'2'})

        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent2, 'priority':'0', 'order':'2'})

    def test_add_parent5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.child1.add_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.add_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 2)
        self.assertDictEqual(self.child1.parents[1], {'parent':self.parent1, 'priority':'0', 'order':'2'})

        self.child1.add_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.parents), 2, "not delete parent1 due to the same priority")

        self.child1.add_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.parents), 1, "successfully delete parent1")
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})


    def test_preserve_parent1(self):
        "add parent and add parent override"
        self.child1.preserve_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.preserve_parent(self.parent1, '', '1', '2')
        self.assertEqual(len(self.child1.parents), 2, "after adding second parent")
        self.assertDictEqual(self.child1.parents[1], {'parent':self.parent1, 'priority':'1', 'order':'2'})

    def test_preserve_parent2(self):
        "add parent1 prohibited and add parent1 with same order and parent1 with different order"
        self.child1.preserve_parent(self.parent1, 'prohibited', '1', '1')
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'1', 'order':'1'})

        self.child1.preserve_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.parents), 1)

        self.child1.preserve_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})

    def test_preserve_parent3(self):
        "add parent1 prohibited and add parent1 with different order and add prent1 with same order"
        self.child1.preserve_parent(self.parent1, 'prohibited', '1', '1')
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'1', 'order':'1'})

        self.child1.preserve_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})

        self.child1.preserve_parent(self.parent1, '', '0', '1')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})

    def test_preserve_parent4(self):
        "add parent1 and add parent1 prohibited and add prent1 with different order"
        self.child1.preserve_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.preserve_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.preserve_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.prohibited, {'parent':self.parent1, 'priority':'1', 'order':'1'})
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.preserve_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 1,)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})


    def test_preserve_parent5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.child1.preserve_parent(self.parent1, '', '0', '1')
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'1'})

        self.child1.preserve_parent(self.parent1, '', '0', '2')
        self.assertEqual(len(self.child1.parents), 2)
        self.assertDictEqual(self.child1.parents[1], {'parent':self.parent1, 'priority':'0', 'order':'2'})

        self.child1.preserve_parent(self.parent1, 'prohibited', '0', '1')
        self.assertEqual(len(self.child1.parents), 2, "not delete parent1 due to the same priority")

        self.child1.preserve_parent(self.parent1, 'prohibited', '1', '1')
        self.assertEqual(len(self.child1.parents), 1)
        self.assertDictEqual(self.child1.parents[0], {'parent':self.parent1, 'priority':'0', 'order':'2'})


    def test_add_derive1(self):
        "add parent and add parent override"
        self.child1.add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})

        self.child1.add_derive(self.parent1, '', '1', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2, "after adding second parent")
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'1', 'order':'2', 'use':'', 'weight':'2.0'})

    def test_add_derive2(self):
        "add parent1 and add parent2 and add prent1 prohibited"
        self.child1.add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})

        self.child1.add_derive(self.parent2, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent2, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

        self.child1.add_derive(self.parent1, 'prohibited', '0', '1', '1.5')
        self.assertEqual(len(self.child1.derives), 2, "not delete parent1 due to the same priority")

        self.child1.add_derive(self.parent1, 'prohibited', '1', '1', '1.6')
        self.assertEqual(len(self.child1.derives), 1, "not delete parent1 due to the same priority")
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent2, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

    def test_add_derive3(self):
        "add parent1 prohibited and add parent1 and parent2"
        self.child1.add_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})

        self.child1.add_derive(self.parent1, '', '0', '1', '1.5')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})

        self.child1.add_derive(self.parent2, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent2, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

    def test_add_derive4(self):
        "add parent1 prohibited and add parent2 and add prent1"
        self.child1.add_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})

        self.child1.add_derive(self.parent2, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent2, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

        self.child1.add_derive(self.parent1, '', '0', '1', '1.5')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent2, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

    def test_add_derive5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.child1.add_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})

        self.child1.add_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

        self.child1.add_derive(self.parent1, 'prohibited', '0', '1', '1.5')
        self.assertEqual(len(self.child1.derives), 2, "not delete parent1 due to the same priority")
        # self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})

        self.child1.add_derive(self.parent1, 'prohibited', '1', '1', '1.6') # cares the orde, not cares the weight
        self.assertEqual(len(self.child1.derives), 1, "successfully delete parent1")
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})


    # def test_preserve_derive1(self):
    #     "add parent and add parent override"
    #     self.child1.preserve_derive(self.parent1, '', '0', '1', '1.0')
    #     self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
    #     self.assertEqual(self.parent1.children_count, 1)

    #     self.child1.preserve_derive(self.parent1, '', '1', '2', '2.0')
    #     self.assertEqual(len(self.child1.derives), 2, "after adding second parent")
    #     self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'1', 'order':'2', 'use':'', 'weight':'2.0'})
    #     self.assertEqual(self.parent1.children_count, 1)

    def test_preserve_derive2(self):
        "add parent1 prohibited and add parent1 with same order and parent1 with different order"
        self.child1.preserve_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 0)

        self.child1.preserve_derive(self.parent1, '', '0', '1', '1.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 1)

    def test_preserve_derive3(self):
        "add parent1 prohibited and add parent1 with different order and add prent1 with same order"
        self.child1.preserve_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 0)

        self.child1.preserve_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, '', '0', '1', '1.0')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 1)

    def test_preserve_derive4(self):
        "add parent1 and add parent1 prohibited and add prent1 with different order"
        self.child1.preserve_derive(self.parent1, '', '0', '1', '1.0')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, 'prohibited', '0', '1', '1.0')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, 'prohibited', '1', '1', '1.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'1', 'order':'1', 'use':'prohibited', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 1)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 1)

    def test_preserve_derive5(self):
        "add parent1 and add parent1 with order and add prent1 prohibited"
        self.child1.preserve_derive(self.parent1, '', '0', '1', '1.0')
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertEqual(self.parent1.derived_count, 1)

        self.child1.preserve_derive(self.parent1, '', '0', '2', '2.0')
        self.assertEqual(len(self.child1.derives), 2)
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 2)

        self.child1.preserve_derive(self.parent1, 'prohibited', '0', '1', '1.5')
        self.assertEqual(len(self.child1.derives), 2, "not delete parent1 due to the same priority")
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'1', 'use':'', 'weight':'1.0'})
        self.assertDictEqual(self.child1.derives[1], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 2)

        self.child1.preserve_derive(self.parent1, 'prohibited', '1', '1', '1.6') # cares the orde, not cares the weight
        self.assertEqual(len(self.child1.derives), 1, "successfully delete parent1")
        self.assertDictEqual(self.child1.derives[0], {'target':self.parent1, 'priority':'0', 'order':'2', 'use':'', 'weight':'2.0'})
        self.assertEqual(self.parent1.derived_count, 1)
