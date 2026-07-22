const complements: Record<string, string> = {
  A:"T", B:"V", C:"G", D:"H", G:"C", H:"D", K:"M", M:"K",
  N:"N", R:"Y", S:"S", T:"A", U:"A", V:"B", W:"W", Y:"R"
};
let input = "";
process.stdin.setEncoding("ascii");
process.stdin.on("data", chunk => input += chunk);
process.stdin.on("end", () => {
  const records = input.split(/^>/m).filter(Boolean);
  let output = "";
  for (const record of records) {
    const newline = record.indexOf("\n");
    const header = record.slice(0, newline).replace(/\r$/, "");
    const sequence = record.slice(newline + 1).replace(/\s/g, "").toUpperCase();
    let reversed = "";
    for (let i = sequence.length - 1; i >= 0; i--) reversed += complements[sequence[i]] || sequence[i];
    output += `>${header}\n`;
    for (let i = 0; i < reversed.length; i += 60) output += reversed.slice(i, i + 60) + "\n";
  }
  process.stdout.write(output);
});
