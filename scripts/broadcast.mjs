/* Keep the public transaction hash even if the RPC reply is lost. */
import { appendFileSync, closeSync, fsyncSync, openSync } from "node:fs";

export async function broadcastWithJournal(parameters, send, journal) {
  const { path, expectedHash, method, id } = journal;
  if (!/^0x[0-9a-f]{64}$/i.test(expectedHash)) throw new Error("invalid expected EVM hash");
  function checkpoint(state) {
    const descriptor = openSync(path, "a");
    try {
      appendFileSync(descriptor, JSON.stringify({ method, id, evm_tx: expectedHash, state }) + "\n");
      fsyncSync(descriptor);
    } finally { closeSync(descriptor); }
  }
  checkpoint("broadcast_attempt");
  const hash = await send(parameters);
  if (typeof hash !== "string" || hash.toLowerCase() !== expectedHash.toLowerCase()) {
    throw new Error("RPC returned an unexpected EVM transaction hash");
  }
  checkpoint("broadcast_acknowledged");
  return hash;
}
