// The search ranks the pages written for a builder or a user above the engineering notes: a design document
// (a file directly under docs/) holds the same words many times over, and would otherwise come first.
var Scorer = {
  score: (result) => {
    const [docname, , , , score] = result;
    return docname.includes("/") || docname === "index" ? score : score * 0.35;
  },
  objNameMatch: 11,
  objPartialMatch: 6,
  objPrio: { 0: 15, 1: 5, 2: -5 },
  objPrioDefault: 0,
  title: 15,
  partialTitle: 7,
  term: 5,
  partialTerm: 2,
};
