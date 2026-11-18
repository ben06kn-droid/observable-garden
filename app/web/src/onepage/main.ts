// The one-page site's one script (index.html, run.html, docs.html, sancho.html, eucalyptus.html: the same document at each address). boot.ts first, so
// the loading screen and the work count are there before any section registers its work; then each section's
// script in page order; then start().
import "../common";              // the shared stylesheet first, so the themes win ties
import { start } from "./boot";
import "../pages/index";
import "../pages/run";
import "../pages/docs";
import "../pages/sancho";
import "../pages/eucalyptus";
start();
