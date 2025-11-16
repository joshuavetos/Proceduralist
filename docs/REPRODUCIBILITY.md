# Reproducibility Auditor

The reproducibility auditor verifies that the ledger, Merkle state, and the
pinned toolchain (requirements.txt) have not drifted.

1. Hash each artifact using `tessrax.core.hashing.DeterministicHasher`.
2. Compare the digests and alert if any artifact matches a known compromised
   digest or diverges from the expected reference set.
3. Emit a structured JSON report that is uploaded to Codecov via CI.

Run the audit locally:

```bash
python -m tessrax.cli.tessraxctl repro-audit
```

To guard a deployment pipeline, persist trusted ledger digests and invoke
`reproducibility_guard(reference_hashes=<trusted>, ledger_path=<path>)`.
