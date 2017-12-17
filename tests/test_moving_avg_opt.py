"""Tests for moving_average_optimizer."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os.path
import tempfile
import six
import tensorflow as tf

from tefla.core.optimizer import MovingAverageOptimizer


class MovingAverageOptimizerTest(tf.test.TestCase):

    def testRun(self):
        for sequential_update in [True, False]:
            for dtype in [tf.half, tf.float32, tf.float64]:
                with self.test_session() as sess:
                    orig_val0 = [1.0, 2.0]
                    orig_val1 = [3.0, 4.0]
                    var0 = tf.Variable(
                        orig_val0, name='var0', dtype=dtype)
                    var1 = tf.Variable(
                        orig_val1, name='var1', dtype=dtype)
                    grads0 = tf.constant([0.1, 0.1], dtype=dtype)
                    grads1 = tf.constant([0.01, 0.01], dtype=dtype)

                    opt = MovingAverageOptimizer(
                        tf.train.GradientDescentOptimizer(
                            learning_rate=2.0),
                        average_decay=0.5,
                        sequential_update=sequential_update)
                    save_dir = tempfile.mkdtemp(
                        prefix=os.path.join(self.get_temp_dir(), 'run_1'))
                    save_path = os.path.join(save_dir, 'model')
                    update = opt.apply_gradients(
                        list(six.moves.zip([grads0, grads1], [var0, var1])))
                    train_saver = opt.swapping_saver()
                    inference_saver = tf.train.Saver()
                    tf.global_variables_initializer().run()
                    # Step 1.
                    update.run()
                    val0 = var0.eval()
                    val1 = var1.eval()
                    self.assertAllCloseAccordingToType([0.8, 1.8], var0.eval())
                    self.assertAllCloseAccordingToType(
                        [2.98, 3.98], var1.eval())
                    # Test that the swapping saver save/restore operation is identity.
                    train_saver.save(sess, save_path)
                    train_saver.restore(sess, save_path)
                    val0 = var0.eval()
                    val1 = var1.eval()
                    self.assertAllCloseAccordingToType([0.8, 1.8], var0.eval())
                    self.assertAllCloseAccordingToType(
                        [2.98, 3.98], var1.eval())
                    # If updates are parallel, this is not always true after the 1st step.
                    if sequential_update:
                        # Test that the normal saver will have the averaged variables.
                        # We test that the average values are between the original value
                        # and the most recent variable values (since they are an average
                        # of the two).
                        val0 = var0.eval()
                        val1 = var1.eval()
                        train_saver.save(sess, save_path)
                        inference_saver.restore(sess, save_path)
                        avg_val0 = var0.eval()
                        avg_val1 = var1.eval()
                        for i in six.moves.range(len(val0)):
                            self.assertLess(val0[i], avg_val0[i])
                            self.assertLess(avg_val0[i], orig_val0[i])
                            self.assertLess(val1[i], avg_val1[i])
                            self.assertLess(avg_val1[i], orig_val1[i])
                        train_saver.restore(sess, save_path)
                    # Step 2.
                    update.run()
                    # Test that the normal saver will have the averaged variables.
                    # We test that the average values are between the original value and
                    # the most recent variable values (since they are an average of the
                    # two).
                    val0 = var0.eval()
                    val1 = var1.eval()
                    self.assertAllCloseAccordingToType([0.6, 1.6], val0)
                    self.assertAllCloseAccordingToType([2.96, 3.96], val1)
                    train_saver.save(sess, save_path)
                    inference_saver.restore(sess, save_path)
                    avg_val0 = var0.eval()
                    avg_val1 = var1.eval()
                    for i in six.moves.range(len(val0)):
                        self.assertLess(val0[i], avg_val0[i])
                        self.assertLess(avg_val0[i], orig_val0[i])
                        self.assertLess(val1[i], avg_val1[i])
                        self.assertLess(avg_val1[i], orig_val1[i])

    def testFailWhenSaverCreatedBeforeInitialized(self):
        with self.test_session():
            var = tf.Variable([1.0], name='var', dtype=tf.float32)
            opt = MovingAverageOptimizer(
                tf.train.GradientDescentOptimizer(learning_rate=2.0))
            # We didn't call apply_gradients yet.
            # This will raise an exception.
            with self.assertRaises(RuntimeError):
                _ = opt.swapping_saver([var])

    def testCorrectOverride(self):

        class WrapperOptimizer(tf.train.GradientDescentOptimizer):

            def compute_gradients(self, *args, **kwargs):
                self.compute_gradients_called = True
                return super(WrapperOptimizer, self).compute_gradients(
                    *args, **kwargs)

            def apply_gradients(self, *args, **kwargs):
                self.apply_gradients_called = True
                return super(WrapperOptimizer, self).apply_gradients(*args, **kwargs)

        with self.test_session() as sess:
            var = tf.Variable([1.2], name='var', dtype=tf.float32)
            loss = var ** 2
            wrapper_opt = WrapperOptimizer(learning_rate=2.0)
            opt = MovingAverageOptimizer(wrapper_opt)
            train_op = opt.minimize(loss)

            # Check that both methods are called on the underlying optimizer.
            self.assertTrue(wrapper_opt.compute_gradients_called)
            self.assertTrue(wrapper_opt.apply_gradients_called)

            # Run train_op once, and verify that we've updated the variable.
            tf.global_variables_initializer().run()
            sess.run(train_op)
            var_value = sess.run(var)
            # Started at 1.2, gradient is 2*1.2=2.4, lr=2, so should now be -3.6.
            self.assertNear(-3.6, var_value, 1e-6)


if __name__ == '__main__':
    tf.test.main()
