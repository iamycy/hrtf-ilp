import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, eye, diags, find
from typing import Tuple, Iterable
from qpsolvers import solve_qp


def solve_linprog(
    edges: np.ndarray,
    simplices: Iterable[Iterable[int]],
    differences: np.ndarray,
    c: np.ndarray = None,
    fixed_k_mask: np.ndarray = None,
    adaptive_weights: bool = False,
    **options,
) -> np.ndarray:
    """
    This function assumes the solutions and the targets are integers.

    Args:
        edges: (M, 2)
        simplices: (N, *)
        weights: (M,)
    """
    M, N = edges.shape[0], len(simplices)

    edge_dict = {tuple(x): i for i, x in enumerate(edges)}
    rows = []
    cols = []
    vals = []
    for i, simplex in enumerate(simplices):
        u = simplex[-1]
        for v in simplex:
            key = (u, v)
            rows.append(i)
            if key in edge_dict:
                cols.append(edge_dict[key])
                vals.append(1)
            else:
                cols.append(edge_dict[(v, u)])
                vals.append(-1)
            u = v

    rows = np.array(rows)
    cols = np.array(cols)
    vals = np.array(vals)

    V = csr_matrix((vals, (rows, cols)), shape=(N, M))
    y = V @ differences

    if fixed_k_mask is not None:
        nonzero_cols = np.nonzero(~fixed_k_mask)[0]
        unique_cols_dict = {x: i for i, x in enumerate(nonzero_cols)}
        filtered_rows = []
        filtered_cols = []
        filtered_vals = []
        for i, (row, col, val) in enumerate(zip(rows, cols, vals)):
            if col in unique_cols_dict:
                filtered_rows.append(row)
                filtered_cols.append(unique_cols_dict[col])
                filtered_vals.append(val)

        unique_rows, rows_inv = np.unique(filtered_rows, return_inverse=True)
        rows = np.arange(len(unique_rows))[rows_inv]
        y = y[unique_rows]
        cols = np.array(filtered_cols)
        vals = np.array(filtered_vals)

        V = csr_matrix(
            (vals, (rows, cols)),
            shape=(len(unique_rows), len(nonzero_cols)),
        )

        N, M = V.shape
        if c is not None:
            c = c[~fixed_k_mask]

    y = np.round(y).astype(np.int64)

    # print("Number of non-zero simplices:", np.count_nonzero(y))
    # print("L1 norm of non-zero simplices:", np.abs(y).sum())

    A_eq = csr_matrix(
        (
            np.concatenate((vals, -vals)),
            (np.tile(rows, 2), np.concatenate((cols, cols + M))),
        ),
        shape=(N, M * 2),
    )
    b_eq = -y

    if c is None:
        if adaptive_weights:
            c = np.abs(A_eq).T @ np.abs(b_eq)
            c = np.where(c == 0, 1, 0).astype(np.int64)
        else:
            c = np.ones((M * 2,), dtype=np.int64)
    else:
        c = np.tile(c, 2)

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, integrality=1, options=options)
    k = res.x[:M] - res.x[M:]
    k = k.astype(np.int64)
    cost = np.abs(V @ k + y).sum()
    assert cost == 0, f"cost is {cost}"
    return k


def solve_quadprog(
    edges: np.ndarray,
    simplices: Iterable[Iterable[int]],
    differences: np.ndarray,
    c: np.ndarray = None,
    **options,
) -> np.ndarray:
    """
    This function assumes the targets are integers.

    Args:
        edges: (M, 2)
        simplices: (N, *)
        weights: (M,)
    """
    M, N = edges.shape[0], len(simplices)

    edge_dict = {tuple(x): i for i, x in enumerate(edges)}
    rows = []
    cols = []
    vals = []
    for i, simplex in enumerate(simplices):
        u = simplex[-1]
        for v in simplex:
            key = (u, v)
            rows.append(i)
            if key in edge_dict:
                cols.append(edge_dict[key])
                vals.append(1)
            else:
                cols.append(edge_dict[(v, u)])
                vals.append(-1)
            u = v

    rows = np.array(rows)
    cols = np.array(cols)
    vals = np.array(vals)

    V = csr_matrix((vals, (rows, cols)), shape=(N, M))
    y = V @ differences
    y = np.round(y).astype(np.int64)

    A_eq = V
    b_eq = -y

    if c is None:
        P = eye(M, format="csc")
    else:
        P = diags(c, format="csc")

    k = solve_qp(P, np.zeros((M,)), A=A_eq, b=b_eq, solver="highs")
    cost = np.abs(V @ k + y).sum()
    print(f"Final cost is {cost}")
    return k
