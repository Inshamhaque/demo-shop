# Demo shop

A small order service used as the target codebase for batpatcher AI. It has planted bugs:

- **Loud bug:** `build_summary` crashes with `TypeError` when `discount` is missing (`None`). Nothing in the tests covers it.
- **Silent bug:** when `coupon` is set, the discount is applied again even if `discount_applied` is true. No error is raised; the total is just wrong.
- **Financial bug:** monetary inputs are not validated or rounded. A discount greater than 100% or a negative order total can produce a negative payable amount; fractional results can also include sub-cent values.

`invoice_service` reads the summary's `total` as a number. A patch that changes its type breaks it, even when the shop's own tests pass.

Run the tests from this folder:

```bash
python -m pytest -q
```

Expected: 3 passed. The shop tests do not cover the planted bugs.
