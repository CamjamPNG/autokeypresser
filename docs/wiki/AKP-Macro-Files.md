# AKP Macro Files

`.akp` is the proprietary AutoKeyPresser Macro format. It contains a format
signature, version byte, JSON action payload, and SHA-256 checksum.

AutoKeyPresser rejects files that do not have the correct signature, supported
version, valid payload, or checksum. The format is integrity-protected, not
encrypted.
