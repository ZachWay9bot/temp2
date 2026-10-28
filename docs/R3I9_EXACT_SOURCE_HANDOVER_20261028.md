# R3I9 exact source handover — 2026-10-28

Authoritative next-development base for R3I10+:

- Build ID: `G30D-FO76-PUSHSTART-R3I9`
- Exact source archive: `SOURCE_KOXX3_R3I9_EXACT.tgz`
- Exact source bytes: `139086259`
- Exact source SHA256: `d059badd542236e7d679b8433b37f2c1ae5ae56896283a22a9cf55c23034b5a2`
- Matching BIN bytes: `88352`
- Matching BIN SHA256: `43a37750c73c1f40c5b77cee8774602580f6b77901c9a3fd8f29d20366b8aeb1`
- CI run: `40715698181`
- CI artifact: `12828690987`
- Branch: `r3i9-live-hall-cal-20261028`
- Workflow head: `5c52801215adf3b81490b1477200e167759dde63`
- Embedded upstream Git HEAD: `272bdb99d75484dcc377e1cf3e6a20e53a6fd8de`

## Binding handover rule

For R3I10 and later firmware changes, unpack the exact source archive above and continue from that tree. Do not reconstruct the next version from the Koxx3 upstream base or from an older R3I overlay unless explicitly requested.

The embedded `.git/HEAD` identifies only the upstream Koxx3 base. R3G/R3H/R3I through R3I9 are present as worktree changes inside the archived source tree. Therefore the SHA256 of the complete TGZ is the authoritative identity of the R3I9 source handover.

Matching compiler: xPack GNU Arm Embedded GCC 13.2.1.
