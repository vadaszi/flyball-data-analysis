/* Line-up scoring for the website: a line-by-line port of flyball.lineup.score_orders.
   `make(model)` takes the arrays exported by flyball.report.site.lineup_model (window.WRFT.model).
   tests/test_phase6.py runs this file under Node and compares it with the Python scores. */
(function (root) {
  "use strict";
  function make(M) {
    const byName = Object.fromEntries(M.dogs.map((d, i) => [d.name, i]));

    function score(names) {
      const ds = names.map(n => M.dogs[byName[n]]);
      const h = Math.min(...ds.map(d => d.h));                       // the smallest dog sets the hurdle
      const runs = ds.reduce((s, d, i) => s + d.run[h][i], 0);
      const starter = ds[0];
      const start = starter.start === null ? starter.start_any : starter.start;
      const passes = ds.slice(1).reduce((s, d) => s + d.pass, 0);
      const nf = starter.fs + ds.slice(1).reduce((s, d) => s + d.ep, 0) + ds.reduce((s, d) => s + d.rf, 0);
      const pClean = (1 - starter.fs) * ds.slice(1).reduce((p, d) => p * (1 - d.ep), 1) * ds.reduce((p, d) => p * (1 - d.rf), 1);
      const clean = start + runs + passes;
      return { expected: clean + M.fault_cost * nf, noFault: clean, start, runs, passes, fault: M.fault_cost * nf, nf, pClean,
               hurdle: M.heights[h], starterOk: starter.start !== null };
    }

    function permutations(a) {
      if (a.length <= 1) return [a];
      return a.flatMap((x, i) => permutations([...a.slice(0, i), ...a.slice(i + 1)]).map(p => [x, ...p]));
    }

    function bestOrder(names) {                                      // only proven starters open, as in Python
      let best = null;
      for (const p of permutations(names)) {
        if (M.dogs[byName[p[0]]].start === null) continue;
        const s = score(p);
        if (!best || s.expected < best.s.expected) best = { p, s };
      }
      return best ? best.p : names;
    }
    return { score, bestOrder };
  }
  root.WRFTLineup = { make };
})(typeof window !== "undefined" ? window : globalThis);
