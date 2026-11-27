// The provider reports UI events. Only a separate, verified server callback may credit a real account.
export function watchRewarded(tag, path, handlers) {
  let slot;
  let service;
  let timer;
  let started = false;
  let granted = false;
  let ended = false;
  const listeners = {
    rewardedSlotReady: event => {
      clearTimeout(timer);
      handlers.ready(() => {
        if (ended || started) return;
        try {
          started = true;
          if (!event.makeRewardedVisible()) finish('unavailable');
        } catch { finish('unavailable'); }
      });
    },
    rewardedSlotGranted: () => {
      if (started && !granted) {
        granted = true;
        handlers.granted();
      }
    },
    rewardedSlotClosed: () => finish(granted ? 'complete' : 'closed'),
    // Completion of the video alone is not a reward.
    rewardedSlotVideoCompleted: () => {},
  };
  const attached = [];
  function finish(reason) {
    if (ended) return;
    ended = true;
    clearTimeout(timer);
    for (const [type, listener] of attached) service.removeEventListener(type, listener);
    if (slot) tag.destroySlots([slot]);
    handlers.end(reason);
  }
  timer = setTimeout(() => finish('unavailable'), 8000);
  tag.cmd.push(() => {
    if (ended) return;
    try {
      slot = tag.defineOutOfPageSlot(path, tag.enums.OutOfPageFormat.REWARDED);
      if (!slot) return finish('unavailable');
      service = tag.pubads();
      for (const [type, callback] of Object.entries(listeners)) {
        const listener = event => {
          if (event.slot === slot && !ended) callback(event);
        };
        service.addEventListener(type, listener);
        attached.push([type, listener]);
      }
      slot.addService(service);
      tag.enableServices();
      tag.display(slot);
    } catch { finish('unavailable'); }
  });
  return () => finish('closed');
}

export function simulatedTag(available) {
  const listeners = new Map();
  const slot = {addService() {}};
  const emit = (type, extra) => listeners.get(type)?.({slot, ...extra});
  let timer;
  const service = {
    addEventListener(type, listener) { listeners.set(type, listener); },
    removeEventListener(type) { listeners.delete(type); },
  };
  return {
    cmd: {push: callback => queueMicrotask(callback)},
    enums: {OutOfPageFormat: {REWARDED: 'rewarded'}},
    defineOutOfPageSlot: () => available ? slot : null,
    pubads: () => service,
    enableServices() {},
    display() {
      emit('rewardedSlotReady', {makeRewardedVisible() {
        timer = setTimeout(() => {
          emit('rewardedSlotVideoCompleted');
          emit('rewardedSlotGranted');
          emit('rewardedSlotGranted');
          emit('rewardedSlotClosed');
        }, 1500);
        return true;
      }});
    },
    destroySlots() { clearTimeout(timer); },
  };
}
