# Quotivate – Civic Complaint Management System

Quotivate is a civic-tech platform that streamlines lodging, tracking, and resolving public complaints.  
It connects **citizens**, **officers**, **senior officers**, and **administrators** in one ecosystem, ensuring efficient **auto-assignment** of complaints to the right authority based on location, issue type, and workload.

---

## 🚀 Features

- **Citizen Module** – File complaints, attach images, pin locations on Google Maps, track complaint status.
- **Officer Module** – View assigned complaints, update progress, mark resolution.
- **Senior Officer Module** – Monitor escalations, reassign complaints, oversee city-wide progress.
- **Admin Module** – Manage users, cities, zones, complaint types, and system settings.
- **Auto-Assignment Logic** – Assigns complaints automatically based on:
  - City
  - Issue Type
  - Least workload
- **GeoJSON Integration** – Stores cities and zones with boundary data for accurate location mapping.
- **Google Maps Integration** – Users can pin complaint locations; system auto-fills city/zone details.
- **Image Upload Support** – Attach supporting images with complaints.

---

## 🛠 Tech Stack

**Frontend:** HTML, CSS, JavaScript  
**Backend:** Python (Flask)  
**Database:** MySQL  
**Maps & Geo:** Google Maps API, GeoJSON  
**Other Tools:** APScheduler, Folium
