"""
Sensitivity analysis implementations for kernel sparsity on Graphs against loss funcs.
"""

from typing import Dict, List, Union, Callable, Tuple
from collections import namedtuple
import numpy
from tqdm import auto

from neuralmagicML.recal import KSLossSensitivityAnalysis, default_check_sparsities_loss
from neuralmagicML.tensorflow.utils import tf_compat
from neuralmagicML.tensorflow.utils import get_ops_and_inputs_by_name_or_regex
from neuralmagicML.tensorflow.recal.mask_ks import KSScope, create_op_pruning
from neuralmagicML.tensorflow.recal.sparsity_mask import (
    SparsityMaskCreator,
    load_mask_creator,
)


__all__ = [
    "SparsePruningOpVars",
    "approx_ks_loss_sensitivity",
    "ks_loss_sensitivity_op_vars",
    "one_shot_ks_loss_sensitivity",
]


SparsePruningOpVars = namedtuple("SparsePruningOpVars", ("op_vars", "sparsity"))


def ks_loss_sensitivity_op_vars(
    graph: tf_compat.Graph = None,
    var_names: Union[List[str], Tuple[str]] = ("re:.*",),
    mask_type: Union[str, List[int], SparsityMaskCreator] = "unstructured",
) -> List[SparsePruningOpVars]:
    """
    Edit the graph for to inject pruning ops and vars to allow for a ks loss
    sensitivity analysis.

    Note: this must be run outside of a session for it to take effect.

    :param graph: the graph to inject pruning ops and vars into,
        if not supplied uses get_default_graph()
    :param var_names: List of variable names or regex patterns of variables to get
        the op vars for.  Defaults to matching all variables
    :param mask_type: String to define type of sparsity (options: ['unstructured',
        'channel', 'filter']), List to define block shape of a parameter's in and out
        channels, or a SparsityMaskCreator object. default is 'unstructured'
    :return: the created pruning op vars to be used in approx_ks_loss_sensitivity and
        one_shot_ks_loss_sensitivity
    """

    if not graph:
        graph = tf_compat.get_default_graph()

    mask_creator = mask_type
    if not isinstance(mask_type, SparsityMaskCreator):
        mask_creator = load_mask_creator(mask_type)

    ks_group = one_shot_ks_loss_sensitivity.__name__
    prunable_ops_and_inputs = get_ops_and_inputs_by_name_or_regex(var_names, graph)
    op_vars = []

    with graph.as_default():
        for prune_op, prune_op_input in prunable_ops_and_inputs:
            with tf_compat.name_scope(
                KSScope.model(prune_op, ks_group, trailing_slash=True)
            ):
                sparsity = tf_compat.placeholder(
                    dtype=tf_compat.float32, name="sparsity_placeholder"
                )
                update = tf_compat.constant(True, tf_compat.bool)
            prune_op_var = create_op_pruning(
                prune_op,
                prune_op_input,
                sparsity,
                update,
                True,
                None,
                ks_group,
                mask_creator,
            )
            op_vars.append(SparsePruningOpVars(prune_op_var, sparsity))

    return op_vars


def approx_ks_loss_sensitivity(
    graph: tf_compat.Graph = None,
    sess: tf_compat.Session = None,
    sparsity_levels: Union[
        List[float], Tuple[float, ...]
    ] = default_check_sparsities_loss(True),
) -> KSLossSensitivityAnalysis:
    """
    Approximated kernel sparsity (pruning) loss analysis for a given model.
    Returns the results for each prunable param (conv, linear) in the model.
    Approximated by taking the magnitudes of the weights.

    :param graph: the graph to inject pruning ops and vars into,
        if not supplied uses get_default_graph()
    :param sess: the session to use
    :param sparsity_levels: the sparsity levels to calculate the loss for for each param
    :return: the analysis results for the model
    """

    if not graph:
        graph = tf_compat.get_default_graph()
    if not sess:
        sess = tf_compat.get_default_session()

    prunable_ops_and_inputs = get_ops_and_inputs_by_name_or_regex(["re:.*"], graph)
    analysis = KSLossSensitivityAnalysis()

    for op_index, (_, op_tens) in enumerate(prunable_ops_and_inputs):
        weight = sess.run(op_tens)
        values = numpy.sort(numpy.abs(weight.reshape(-1)))
        prev_index = None

        for sparsity in sparsity_levels:
            val_index = round(sparsity * len(values))

            if val_index >= len(values):
                val_index = len(values) - 1

            if sparsity <= 1e-9:
                analysis.add_result(
                    None, op_tens.name, op_index, 0.0, 0.0, baseline=True
                )
            else:
                avg = (
                    values[prev_index:val_index].mean().item()
                    if val_index > prev_index
                    else values[val_index].item()
                )
                analysis.add_result(
                    None, op_tens.name, op_index, sparsity, avg, baseline=False
                )

            prev_index = val_index + 1

    return analysis


def one_shot_ks_loss_sensitivity(
    op_vars: List[SparsePruningOpVars],
    loss_tensor: tf_compat.Tensor,
    steps_per_measurement: int,
    add_ops_creator: Callable[[int], List[tf_compat.Tensor]] = None,
    feed_dict_creator: Callable[[int], Dict[str, tf_compat.Tensor]] = None,
    sess: tf_compat.Session = None,
    sparsity_levels: List[int] = default_check_sparsities_loss(False),
    show_progress: bool = True,
) -> KSLossSensitivityAnalysis:
    """
    Run a one shot sensitivity analysis for kernel sparsity.
    It does not retrain, and instead puts the model to eval mode.
    Moves operation by operation to calculate the sensitivity analysis for each and
    resets the previously run layers.
    Subsequent sparsity checks for layers and levels will be much faster.

    Note: this should be run once a session has been created and
    the variables have been created for the model.

    Note: the graph should be recreated for later training as this creates
    extra ops in the graph that should be reused before continuing in the system.

    :param op_vars: the created pruning op vars from ks_loss_sensitivity_op_vars
    :param loss_tensor: the loss tensor in the model to measure for the sensitivity
    :param steps_per_measurement: the number of session.run calls to run through
        for each sparsity level on each layer
    :param add_ops_creator: a callback to create an op/tens list to be run through
        the session for each measurement. Called for each measurement
    :param feed_dict_creator: a callback to create a feed dict to be run through
        the session for each measurement. Called for each measurement
    :param sess: the session to use
    :param sparsity_levels: the sparsity levels to check for each layer to calculate
        sensitivity
    :param show_progress: track progress of the runs if True
    :return: the sensitivity results for every op that is prunable
    """

    if not sess:
        sess = tf_compat.get_default_session()

    analysis = KSLossSensitivityAnalysis()
    sess.run(tf_compat.variables_initializer([var.op_vars.mask for var in op_vars]))
    bar = (
        auto.tqdm(
            desc="KS Analysis",
            total=len(op_vars) * len(sparsity_levels) * steps_per_measurement,
        )
        if show_progress
        else None
    )

    for op_index, sparse_op_vars in enumerate(op_vars):
        for sparsity_level in sparsity_levels:
            sess.run(
                sparse_op_vars.op_vars.update,
                feed_dict={sparse_op_vars.sparsity: sparsity_level},
            )

            for step in range(steps_per_measurement):
                ops = [loss_tensor]
                add_ops = add_ops_creator(step) if add_ops_creator else None
                feed_dict = feed_dict_creator(step) if feed_dict_creator else None

                if add_ops:
                    ops.extend(add_ops)

                values = sess.run(ops, feed_dict=feed_dict)
                loss = values[0]
                analysis.add_result(
                    None,
                    sparse_op_vars.op_vars.op_input.name,
                    op_index,
                    sparsity_level,
                    loss,
                    baseline=sparsity_level < 1e-9,
                )

                if bar is not None:
                    bar.update(1)

        sess.run(
            sparse_op_vars.op_vars.update, feed_dict={sparse_op_vars.sparsity: 0.0}
        )

    if bar is not None:
        bar.close()

    return analysis
