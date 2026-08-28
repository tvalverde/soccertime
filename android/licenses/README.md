# Bundled fonts

`Inter` and `Anybody` are the two faces the website uses, declared in
`soccertime/static/soccertime/css/theme.css`. The apps carry them as files rather than
reaching for Android's downloadable fonts, because that mechanism is served by Google Play
services and a Fire TV has none — on the one device this project exists for, a downloadable
font is a silent fallback to the system sans-serif.

Static instances, one file per weight, and not the variable originals: variable font axes
need API 26 and `minSdk` here is 25, so on the Fire TV a variable file would render every
weight at its default and the whole type hierarchy would flatten.

Both are under the SIL Open Font License 1.1, whose terms are beside this file.
