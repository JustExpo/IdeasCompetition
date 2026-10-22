/** Границы frontend из CLAUDE.md §4.2: pages → features → api | shared; features друг друга не импортируют. */
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      severity: "error",
      comment: "Циклические импорты запрещены.",
      from: {},
      to: { circular: true },
    },
    {
      name: "shared-is-bottom",
      severity: "error",
      comment: "shared не знает ни про api, ни про features, ни про pages, ни про app.",
      from: { path: "^src/shared/" },
      to: { path: "^src/(api|features|pages|app)/" },
    },
    {
      name: "api-is-low-level",
      severity: "error",
      comment: "api не зависит от интерфейса.",
      from: { path: "^src/api/" },
      to: { path: "^src/(features|pages|app)/" },
    },
    {
      name: "features-not-to-pages",
      severity: "error",
      comment: "features не импортируют pages и app.",
      from: { path: "^src/features/" },
      to: { path: "^src/(pages|app)/" },
    },
    {
      name: "features-do-not-import-each-other",
      severity: "error",
      comment: "Фича общается с другими фичами только через pages (композиция).",
      from: { path: "^src/features/([^/]+)/" },
      to: { path: "^src/features/", pathNot: "^src/features/$1/" },
    },
    {
      name: "pages-not-to-app",
      severity: "error",
      comment: "pages не импортируют app.",
      from: { path: "^src/pages/" },
      to: { path: "^src/app/" },
    },
    {
      name: "no-test-code-in-production",
      severity: "error",
      comment: "Тестовые помощники не попадают в сборку.",
      from: { path: "^src/", pathNot: "(\\.test\\.tsx?$|^src/test/)" },
      to: { path: "^src/test/" },
    },
  ],
  options: {
    tsConfig: { fileName: "tsconfig.json" },
    tsPreCompilationDeps: true,
    doNotFollow: { path: "node_modules" },
    exclude: { path: "\\.gen\\.ts$" },
  },
};
