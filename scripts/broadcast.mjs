/* Keep only public recovery data on disk; signed bytes remain in RAM. */
import { appendFileSync, closeSync, existsSync, fsyncSync, openSync, readFileSync } from "node:fs";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export function assertBroadcastReconciled(manifest, { method, id }) {
  const rows = path => {
    if (!existsSync(path)) return [];
    try { return readFileSync(path, "utf8").split("\n").filter(line => line.trim()).map(JSON.parse); }
    catch { throw new Error("Invalid broadcast recovery file; reconciliation required before another SDK send"); }
  };
  const pending = rows(manifest + ".broadcasts.jsonl").filter(row => row.method === method && row.id === id);
  if (!pending.length) return;
  if (rows(manifest).some(row => row.method === method && row.id === id && /^0x[0-9a-f]{64}$/i.test(row.tx || ""))) return;
  const publicHash = pending.at(-1).evm_tx;
  throw new Error("Previous broadcast requires reconciliation before another SDK send" +
    (/^0x[0-9a-f]{64}$/i.test(publicHash || "") ? ": " + publicHash : ""));
}

function capacityDelay(error) {
  // Retry only an explicit RPC rejection, never an ambiguous HTTP failure.
  for (let current = error, depth = 0; current && depth < 8; current = current.cause, depth++) {
    const delay = current.data?.retryAfterMs;
    if (current.code === -32005 && /transaction gas rate limit exceeded|node is at capacity/i.test(current.message || "") &&
        Number.isSafeInteger(delay) && delay >= 0) return delay;
  }
  return null;
}

export async function broadcastWithJournal(parameters, send, journal, options = {}) {
  const { path, expectedHash, method, id } = journal;
  if (!/^0x[0-9a-f]{64}$/i.test(expectedHash)) throw new Error("invalid expected EVM hash");
  const { maxAttempts = 6, baseDelayMs = 100, maxDelayMs = 2000, maxWaitMs = 10000, wait = sleep } = options;
  if (!Number.isSafeInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 10 ||
      ![baseDelayMs, maxDelayMs, maxWaitMs].every(v => Number.isSafeInteger(v) && v >= 0)) throw new Error("invalid broadcast retry bounds");
  const signedParameters = Object.freeze({ ...parameters });
  function checkpoint(state, fields = {}) {
    const descriptor = openSync(path, "a");
    try {
      appendFileSync(descriptor, JSON.stringify({ method, id, evm_tx: expectedHash, state, ...fields }) + "\n");
      fsyncSync(descriptor);
    } finally { closeSync(descriptor); }
  }
  let waitedMs = 0;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    checkpoint("broadcast_attempt", { attempt });
    let hash;
    try {
      hash = await send(signedParameters);
    } catch (error) {
      const requestedDelay = capacityDelay(error);
      if (requestedDelay !== null) {
        const delayMs = Math.max(requestedDelay, Math.min(maxDelayMs, baseDelayMs * 2 ** (attempt - 1)));
        if (attempt < maxAttempts && delayMs <= maxDelayMs && waitedMs + delayMs <= maxWaitMs) {
          checkpoint("capacity_retry", { attempt, delay_ms: delayMs });
          await wait(delayMs);
          waitedMs += delayMs;
          continue;
        }
        checkpoint("capacity_exhausted", { attempt });
        throw new Error("RPC capacity retries exhausted; reconcile EVM hash " + expectedHash + " before another submission");
      }
      checkpoint("broadcast_unacknowledged", { attempt });
      // Never propagate an error that may contain signed request bytes.
      throw new Error("Broadcast not acknowledged; reconcile EVM hash " + expectedHash + " before another submission");
    }
    if (typeof hash !== "string" || hash.toLowerCase() !== expectedHash.toLowerCase()) {
      checkpoint("broadcast_unacknowledged", { attempt });
      throw new Error("RPC returned an unexpected EVM transaction hash; expected " + expectedHash);
    }
    checkpoint("broadcast_acknowledged", { attempt });
    return hash;
  }
}

export function createBroadcastFetch(fetchRpc, options) {
  const { rpcUrl, hashTransaction, parseTransaction, journal, expectedNonce, gasMarginNumerator = 125n, gasMarginDenominator = 100n, retry } = options;
  const endpoint = new URL(rpcUrl).href.replace(/\/$/, "");
  let estimatedGas;
  let estimationFailed = false;
  let attemptedHash;
  return async (input, init) => {
    const url = new URL(typeof input === "string" || input instanceof URL ? input : input.url).href.replace(/\/$/, "");
    if (url !== endpoint || typeof init?.body !== "string") return fetchRpc(input, init);
    const request = JSON.parse(init.body);
    if (request.method === "eth_estimateGas") {
      try {
        const response = await fetchRpc(input, init);
        const payload = await response.clone().json();
        if (!response.ok || payload.error || !/^0x[0-9a-f]+$/i.test(payload.result || "") || BigInt(payload.result) <= 0n) {
          estimationFailed = true;
          return response;
        }
        estimatedGas = (BigInt(payload.result) * gasMarginNumerator + gasMarginDenominator - 1n) / gasMarginDenominator;
        return Response.json({ ...payload, result: "0x" + estimatedGas.toString(16) }, { status: response.status });
      } catch {
        estimationFailed = true;
        throw new Error("RPC gas estimation failed");
      }
    }
    if (request.method === "eth_sendTransaction") throw new Error("Only locally signed raw transactions are permitted");
    if (request.method !== "eth_sendRawTransaction") return fetchRpc(input, init);
    if (estimationFailed || estimatedGas === undefined) throw new Error("Gas estimation failed or was absent; SDK fallback broadcast blocked");
    const signed = request.params?.[0];
    if (request.params?.length !== 1 || !/^0x[0-9a-f]+$/i.test(signed || "")) throw new Error("Invalid signed transaction");
    let parsed, expectedHash;
    try {
      parsed = parseTransaction(signed);
      expectedHash = hashTransaction(signed);
    } catch { throw new Error("Invalid signed transaction; no broadcast occurred"); }
    if (parsed.gas !== estimatedGas) throw new Error("Signed transaction gas differs from the guarded estimate");
    if (expectedNonce !== undefined && BigInt(parsed.nonce) !== BigInt(expectedNonce)) throw new Error("Signed transaction nonce differs from expected_nonce; no broadcast occurred");
    // SDK ABI fallback must not submit a newly signed transaction after an
    // acknowledgement or ambiguous result. Retries stay inside the loop below.
    if (attemptedHash) throw new Error("Another SDK broadcast blocked; reconcile EVM hash " + attemptedHash);
    attemptedHash = expectedHash;
    const broadcastInit = Object.freeze({ ...init, body: init.body });
    let response;
    await broadcastWithJournal({ serializedTransaction: signed }, async () => {
      response = await fetchRpc(input, broadcastInit);
      const payload = await response.clone().json();
      if (!response.ok || payload.error) {
        // This object is consumed internally and never logged or journaled.
        if (payload.error && capacityDelay(payload.error) !== null) throw payload.error;
        throw new Error("RPC raw transaction request failed");
      }
      return payload.result;
    }, { ...journal, expectedHash }, retry);
    return response;
  };
}
