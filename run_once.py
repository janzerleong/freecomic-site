from new_crawler import (
    init_directories, check_disk_space, cleanup_old_files, 
    init_db, fetch_and_store, process_unprocessed_articles, 
    generate_homepage
)

init_directories()
check_disk_space()
cleanup_old_files()
init_db()
fetch_and_store()
process_unprocessed_articles()
generate_homepage()
