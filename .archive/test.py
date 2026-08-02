from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Initialize WebDriver
driver = webdriver.Chrome()

# Load the webpage
driver.get("https://example.com")

# Find the element that needs to be clicked
element = WebDriverWait(driver, 10).until(
   EC.element_to_be_clickable((By.ID, "your_element_id"))
)

# Click the element
element.click()

# Wait for the hidden component to become visible
hidden_component = WebDriverWait(driver, 10).until(
   EC.visibility_of_element_located((By.ID, "hidden_component_id"))
)

# Now you can interact with the visible component
# For example, you can extract text from it
print(hidden_component.text)

# Close the browser
driver.quit()