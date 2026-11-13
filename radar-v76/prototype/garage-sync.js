'use strict';
/* V72: explicit opt-in sync protocol. No endpoint, credentials or network side effects. */
const G = require('./garage');
function assertAdapter(adapter) {
  if (!adapter || typeof adapter.read !== 'function' || typeof adapter.compareAndSwap !== 'function')
    throw new TypeError('adapter must implement read() and compareAndSwap(expectedRevision, next)');
}
function makeMemoryGarageAdapter(initial=G.emptyGarage()) {
  let stored=G.validateGarage(initial);
  return {
    async read(){ return G.validateGarage(stored); },
    async compareAndSwap(expectedRevision,next){
      if (!Number.isSafeInteger(expectedRevision) || expectedRevision<0) throw new TypeError('invalid expectedRevision');
      const candidate=G.validateGarage(next);
      if (candidate.revision!==expectedRevision+1) throw new TypeError('invalid next revision');
      if(stored.revision!==expectedRevision) return {status:'conflict',server:G.validateGarage(stored)};
      stored=candidate;
      return {status:'saved',server:G.validateGarage(stored)};
    }
  };
}
async function synchronizeGarage({local,baseRevision,adapter,signal}={}) {
  assertAdapter(adapter);
  const candidate=G.validateGarage(local);
  if (!Number.isSafeInteger(baseRevision)||baseRevision<0) throw new TypeError('invalid base revision');
  if (signal?.aborted) return {status:'cancelled'};
  const remote=G.validateGarage(await adapter.read());
  if (signal?.aborted) return {status:'cancelled'};
  if (remote.revision!==baseRevision) return {status:'conflict',local:candidate,server:remote};
  if (candidate.revision===baseRevision) return {status:'unchanged',server:remote};
  const prepared=G.prepareSave(candidate,remote,baseRevision);
  if(prepared.status!=='ready') return {status:'conflict',local:candidate,server:remote};
  if (signal?.aborted) return {status:'cancelled'};
  const result=await adapter.compareAndSwap(prepared.expectedRevision,prepared.next);
  if (!result || !['saved','conflict'].includes(result.status)) throw new TypeError('invalid adapter response');
  const server=G.validateGarage(result.server);
  if (result.status==='saved' && (server.revision!==prepared.next.revision || JSON.stringify(server)!==JSON.stringify(prepared.next)))
    throw new TypeError('adapter returned inconsistent saved garage');
  return result.status==='saved'?{status:'saved',server}:{status:'conflict',local:candidate,server};
}
module.exports={makeMemoryGarageAdapter,synchronizeGarage};
