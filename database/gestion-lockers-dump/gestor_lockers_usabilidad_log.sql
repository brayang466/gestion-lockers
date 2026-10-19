-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: gestor_lockers
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `usabilidad_log`
--

DROP TABLE IF EXISTS `usabilidad_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `usabilidad_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `user_nombre` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_email` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_rol` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `area` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `path` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metodo` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accion` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `creado_en` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_usabilidad_log_user_id` (`user_id`),
  KEY `ix_usabilidad_log_creado_en` (`creado_en`),
  CONSTRAINT `usabilidad_log_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usabilidad_log`
--

LOCK TABLES `usabilidad_log` WRITE;
/*!40000 ALTER TABLE `usabilidad_log` DISABLE KEYS */;
INSERT INTO `usabilidad_log` VALUES (1,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard','GET','Dashboard','2026-07-27 20:06:42'),(2,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-27 20:06:46'),(3,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard','GET','Dashboard','2026-07-27 20:06:53'),(4,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/dotaciones-disponibles','GET','Consultó Dotaciones Disponibles','2026-07-27 20:06:56'),(5,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard','GET','Dashboard','2026-07-27 20:07:00'),(6,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-27 20:07:02'),(7,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-27 20:07:17'),(8,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-27 20:07:24'),(9,1,'Brayan Gomez','','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-27 20:07:30'),(10,1,'Brayan Gomez','braaianww@gmail.com','superadmin','','/areas','GET','Selector de áreas','2026-07-28 20:35:20'),(11,1,'Brayan Gomez','braaianww@gmail.com','superadmin','','/entrar-area/BENEFICIO','GET','Entró al área BENEFICIO','2026-07-28 20:35:22'),(12,1,'Brayan Gomez','braaianww@gmail.com','superadmin','BENEFICIO','/dashboard','GET','Dashboard','2026-07-28 20:35:22'),(13,1,'Brayan Gomez','braaianww@gmail.com','superadmin','BENEFICIO','/dashboard/usabilidad','GET','Usabilidad por usuario','2026-07-28 20:35:24'),(14,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','','/areas','GET','Selector de áreas','2026-08-04 18:55:50'),(15,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','','/entrar-area/BENEFICIO','GET','Entró al área BENEFICIO','2026-08-04 18:55:53'),(16,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard','GET','Dashboard','2026-08-04 18:55:53'),(17,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','','/areas','GET','Selector de áreas','2026-08-04 18:56:14'),(18,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','','/entrar-area/BENEFICIO','GET','Entró al área BENEFICIO','2026-08-04 18:56:21'),(19,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard','GET','Dashboard','2026-08-04 18:56:21'),(20,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard','GET','Dashboard','2026-08-04 18:56:34'),(21,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard/registro/registro-personal','GET','Formulario: Personal Pendiente','2026-08-04 18:56:39'),(22,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard','GET','Dashboard','2026-08-04 18:56:43'),(23,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard/registro-asignaciones','GET','Consultó Registro de Asignaciones','2026-08-04 18:56:50'),(24,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard/registro/ingreso-dotacion','GET','Formulario: Ingreso de Dotación','2026-08-04 18:59:20'),(25,3,'Magaly Sandoval','gestor.contratacion@colbeef.com','admin','BENEFICIO','/dashboard/registro/registro-personal','GET','Formulario: Personal Pendiente','2026-08-04 18:59:21');
/*!40000 ALTER TABLE `usabilidad_log` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-07 17:26:36
