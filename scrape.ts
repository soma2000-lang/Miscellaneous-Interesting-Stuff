import { parseArgs } from "jsr:@std/cli/parse-args";
import { Database, Statement } from "jsr:@db/sqlite@0.11";
import * as d3 from "npm:d3-time";
import { parseHTML } from "npm:linkedom";

const months = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];

class Db {
  db: Database;
  #stmtInsertArticle: Statement;

  constructor(path: string) {
    this.db = new Database(path);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS articles(
        id integer primary key autoincrement,
        year integer,
        month integer,
        headline TEXT,
        url TEXT
      )
    `);

    this.#stmtInsertArticle = this.db.prepare(`
      insert into articles(year, month, headline, url)
      select
        :year as year,
        :month as month,
        :headline as headline,
        :url as url
    `);
  }

  insertArticles(
    year: number,
    month: number,
    articles: { url: string; year: number; month: number }[],
  ) {
    const tx = this.db.transaction((year, month, articles) => {
      for (const article of articles) {
        this.#stmtInsertArticle.run({ ...article, year, month });
      }
    });
    tx(year, month, articles);
  }
}

async function insertMonth(db: Db, year: number, month: string) {
  let url = `https://www.nbcnews.com/archive/articles/${year}/${month}`;
  while (true) {
    const monthPage = await fetch(url).then((r) => r.text());
    const { document: monthPageDoc } = parseHTML(monthPage);
    const monthEntries = monthPageDoc
      .querySelectorAll(".MonthPage a")
      .map((a) => ({ headline: a.innerText, url: a.getAttribute("href") }));
    db.insertArticles(
      year,
      months.findIndex((m) => m === month) + 1,
      monthEntries,
    );
    const next = monthPageDoc.querySelector(
      "a.Pagination__next.Pagination__enable",
    );
    if (!next) {
      break;
    }
    url = `https://www.nbcnews.com${next.getAttribute("href")}`;
  }
}

async function backfill(db: Db, start: Date, end: Date) {
  const targets = d3.timeMonths(start, end)
    .map((date) => ({ year: date.getFullYear(), monthIndex: date.getMonth() }));
  for (const target of targets) {
    console.log(`${target.year} ${target.monthIndex}`);
    await insertMonth(db, target.year, months[target.monthIndex]);
  }
}
async function main() {
  const flags = parseArgs(Deno.args, {
    alias: { o: "output" },
    string: ["output", "start", "end"],
  });
  if(!flags.output) {
    console.error("Path to output database required.");
    return;
  }
  if(!flags.start) {
    console.error("Startng date required.");
    return;
  }
  const start = new Date(flags.start);
  const end = flags.end ? new Date(flags.end) : new Date();

  const db = new Db(":memory:");
  await backfill(db, start, end);
  db.db.exec("vacuum into ?", flags.output);
}
if(import.meta.main) {
  main();
}
