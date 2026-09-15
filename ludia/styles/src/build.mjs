import * as esbuild from "esbuild"
import {stimulusPlugin} from "esbuild-plugin-stimulus"

let options = {
  plugins: [stimulusPlugin()],
  entryPoints: ["ludia/styles/src/app.js"],
  bundle: true,
  minify: true,
  outfile: "ludia/styles/static/app.js",
}

if (process.argv.indexOf("watch") !== -1) {
  let ctx = await esbuild.context(options)
  await ctx.watch()
} else {
  await esbuild.build(options)
}
