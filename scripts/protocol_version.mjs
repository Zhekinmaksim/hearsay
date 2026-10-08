/* Deployed Bradbury protocol version proven by the verified implementation. */
export function assertConsensusVersion(version) {
  if (version !== "2.0.0") throw new Error("unverified consensus contract version: " + version);
}
