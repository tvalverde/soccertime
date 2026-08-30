package es.mojon.soccertime.core.ui

/**
 * The site's palette, as plain ARGB values.
 *
 * Lifted from `soccertime/static/soccertime/css/theme.css` rather than picked again: the apps
 * do not copy the web's layout, but they are the same product and a second set of greens
 * would say otherwise. Kept here, without a Compose type, so both applications read one
 * definition and `:core` stays free of the UI toolkit.
 */
object Palette {
    const val BACKGROUND: Long = 0xFF131313
    const val SURFACE: Long = 0xFF1C1B1B
    const val HEADER: Long = 0xFF0E0E0E
    const val SCRIM: Long = 0xFF0A0A0A

    const val HAIRLINE: Long = 0xFF2A2A2A
    const val CARD_BORDER: Long = 0xFF232323
    const val OUTLINE: Long = 0xFF3B4B37
    const val MUTED_OUTLINE: Long = 0xFF4A4A4A

    const val ON_BACKGROUND: Long = 0xFFE5E2E1
    const val ON_BACKGROUND_VARIANT: Long = 0xFFB9CCB2
    const val ON_BACKGROUND_MUTED: Long = 0xFFA29D9B
    const val ON_BACKGROUND_FAINT: Long = 0xFF6F6A68

    /** The loudest thing the agenda can say, reserved for what is on right now. */
    const val PRIMARY: Long = 0xFF00FF41
    const val ON_PRIMARY: Long = 0xFF003907

    /** A channel that can actually be opened. */
    const val SECONDARY: Long = 0xFF00E0FF
    const val ON_SECONDARY: Long = 0xFF00363F

    /**
     * The same cyan behind a chip rather than filling it. Used where the secondary has to read
     * as a state on a dark surface without shouting as loudly as an openable channel does.
     */
    const val SECONDARY_TINT: Long = 0x1F00E0FF

    /** The green behind a chosen option, quieter than the green that means "on now". */
    const val PRIMARY_TINT: Long = 0x1F00FF41

    /** Something the reader chose to follow. */
    const val FAVOURITE: Long = 0xFFFFC107

    const val DANGER: Long = 0xFFFFB4AB
}
