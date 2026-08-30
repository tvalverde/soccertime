package es.mojon.soccertime.core.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The file has to survive two things: a future version of the app writing more than this one
 * knows, and the reader pointing the importer at something that is not an export at all.
 */
class FavoritesTransferTest {

    private val following = Following(
        teams = listOf(FollowedItem(7, "Racing de Santander", "https://www.mojon.es/x.webp")),
        competitions = listOf(FollowedItem(10, "La Liga EA Sports", null)),
    )

    @Test
    fun `what is encoded decodes back whole`() {
        assertEquals(following, FavoritesTransfer.decode(FavoritesTransfer.encode(following)))
    }

    @Test
    fun `a future version's extra fields are ignored, not fatal`() {
        val decoded = FavoritesTransfer.decode(
            """{"version": 9, "teams": [{"id": 7, "name": "Racing de Santander"}], "competitions": [], "colours": true}""",
        )
        assertEquals("Racing de Santander", decoded?.teams?.single()?.name)
    }

    @Test
    fun `anything that is not an export decodes to null, never to an empty success`() {
        // Every envelope field but `version` has a default, so without requiring it any JSON
        // object would import as an empty, "successful" file.
        assertNull(FavoritesTransfer.decode("""{"milk": 2}"""))
        assertNull(FavoritesTransfer.decode("not json at all"))
        assertNull(FavoritesTransfer.decode("[]"))
    }
}
